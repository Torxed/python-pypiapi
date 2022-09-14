import re
import copy
import socket
import ssl
import json
import logging
import pathlib
import urllib.error
import urllib.request
import hashlib
import time
from typing import List
from distutils.version import LooseVersion
from packaging.version import Version, parse as VersionParser, InvalidVersion
from packaging.specifiers import SpecifierSet, InvalidSpecifier

from .storage import storage
from .sockethelpers import epoll, EPOLLIN, EPOLLHUP
from .logger import log
from .licenses import licence_classifier_parser
from .exceptions import VersionError, DependencyError, YankedPackage, InvalidPackage

if storage['arguments'].proxy_host:
	opener = urllib.request.build_opener(
		urllib.request.ProxyHandler({storage['arguments'].proxy_protocol : f"{storage['arguments'].proxy_protocol}://{storage['arguments'].proxy_host}:{storage['arguments'].proxy_port}"})
	)
	urllib.request.install_opener(opener)
	log(f"Added --proxy to all urllib.request", level=logging.INFO, fg="orange")

def safe_version(version):
	# This is escalating..
	return version.replace('>', '').replace('<', '').replace('=', '').replace('~', '').strip()

class Package:
	def __init__(self, name, cache=None):
		if cache is None:
			cache = {}

		self._name = name
		self.cache = cache
		self.destination = None

	def __repr__(self):
		return f"Package(name={self.name}, version={self.cache.get('info', {}).get('version', None)})"

	@property
	def name(self):
		return self._name
	
	@property
	def information(self):
		if not self.cache:
			self.load_information()

		return self.cache

	@property
	def python_version(self):
		if required_python_version := self.information.get('info', {}).get('requires_python', None):
			if storage['arguments'].sort_algorithm == 'LooseVersion':
				return LooseVersion(safe_version(required_python_version))
			elif storage['arguments'].sort_algorithm == 'PackagingVersion':
				return VersionParser(required_python_version)
			elif storage['arguments'].sort_algorithm == 'SpecifierSet':
				return SpecifierSet(required_python_version)

		if storage['arguments'].skip_unknown_py_versions is True:
			raise VersionError(f"Package {self} does not have a python version requirement.")

	@property
	def version(self):
		return self.information.get('info', {}).get('version', None)

	@property
	def license(self):
		return licence_classifier_parser(self.information.get('info', {}).get('classifiers', {}))

	def load_information(self):
		self.set_destination()

		if not self.cache and self.destination.exists() is False:
			log(f"Sending request to https://{storage['arguments'].mirror}{storage['arguments'].json_api}/{self._name}/json", level=logging.DEBUG)
			try:
				request = urllib.request.urlopen(urllib.request.Request(f"https://{storage['arguments'].mirror}{storage['arguments'].json_api}/{self._name}/json", headers={'User-Agent': f"python-pypiapi-{storage['version']}"}))
			except urllib.error.HTTPError as error:
				log(f"Invalid package URL was detected, cannot return inforamtion for {self.name}: {error}", level=logging.ERROR, fg="orange")
				raise InvalidPackage(f"Package URL returned an error '{error.status}' for package: {self.name}")
			self.cache = json.loads(request.read().decode('UTF-8'))
		
		elif self.destination and (self.destination/f"{self._name}.json").exists() and not self.cache:
			with open(f"{self.destination/self._name}.json", "r") as fh:
				self.cache = json.load(fh)
		
		elif self.destination and self.cache:
			if self.destination.exists() is False:
				self.destination.mkdir(parents=True, exist_ok=True)

			with open(f"{self.destination/self._name}.json", "w") as fh:
				json.dump(self.cache, fh)

	def set_destination(self, destination=None):
		if not destination:
			destination = storage['arguments'].destination
		if type(destination) is str:
			destination = pathlib.Path(destination)

		destination = destination/self.name
		self.destination = destination

	def clean_versions(self, versions) -> List[str]:
		clean = []

		# Remove any verions that isn't strictly the format <number>.<number>...-<number>
		for version in versions:
			if any(re.findall(r'[^0-9.\-]', version)) is False:
				clean.append(version)

		return clean

	def versions(self, limit=None):
		if not limit and storage['arguments'].retain_versions:
			limit = int(storage['arguments'].retain_versions)

		try:
			versions = list(self.information.get('releases', {}).keys())
		except InvalidPackage:
			return []

		if not versions:
				return []

		if storage['arguments'].sort_algorithm == 'LooseVersion':
			versions = self.clean_versions(versions)
			try:
				versions.sort(key=LooseVersion)
			except TypeError:
				log(f"Version contains illegal characters: {versions}")
				return []
		elif storage['arguments'].sort_algorithm == 'PackagingVersion':
			try:
				versions.sort(key=VersionParser)
			except TypeError:
				log(f"Version contains illegal characters: {versions}")
				return []
		elif storage['arguments'].sort_algorithm == 'SpecifierSet':
			try:
				versions.sort(key=Version)
			except TypeError:
				log(f"Version contains illegal characters: {versions}")
				return []
			except InvalidVersion:
				log(f"Version contains illegal characters: {versions}")
				return []
		else:
			log(f"Unknown sorting algorithm: {storage['arguments'].sort_algorithm}", level=logging.ERROR, fg="red")
			exit(1)

		versions.reverse()

		if limit and self.version not in versions[:limit]:
			versions.insert(0, self.version)

		return versions[:limit]

	def download(self, version, destination=None, threaded=False, force=False) -> bool:
		self.set_destination(destination)

		if not version in list(self.information.get('releases', {}).keys()):
			raise YankedPackage(f"Package {self.name} does not have a version called: {version}")


		if force is False:
			if storage['arguments'].licenses and any([license in self.license for license in storage['arguments'].licenses]) is False:
				raise DependencyError(f"Package {self.name}'s license {self.license} does not meet the license requirements: {storage['arguments'].licenses}")

			try:
				if storage['arguments'].sort_algorithm == 'SpecifierSet':
					if self.python_version and storage['arguments'].py_version and self.python_version.contains(storage['arguments'].py_version) is False:
						raise DependencyError(f"Package {self.name}'s Python versioning {self.python_version} does not meet the Python version requirements: {storage['arguments'].py_version}")
				else:
					if storage['arguments'].sort_algorithm == 'LooseVersion':
						SelectedVersionHandler = LooseVersion
					elif storage['arguments'].sort_algorithm == 'PackagingVersion':
						SelectedVersionHandler = VersionParser
					if self.python_version and storage['arguments'].py_versions and any([self.python_version >= SelectedVersionHandler(version) for version in storage['arguments'].py_versions]) is False:
						raise DependencyError(f"Package {self.name}'s Python versioning {self.python_version} does not meet the Python version requirements: {storage['arguments'].py_version}")
			except TypeError:
				raise DependencyError(f"Package {self.name}'s Python versioning {self.python_version} does not meet the Python version requirements: {storage['arguments'].py_version}")
			except InvalidSpecifier:
				raise DependencyError(f"Package {self.name}'s Python versioning {self.python_version} does not meet the Python version requirements: {storage['arguments'].py_version}")
			
			except AttributeError as error:
				print(error)
				print(version)
				print(self.cache)
				exit(1)

		if not self.destination.exists():
			try:
				self.destination.mkdir(parents=True, exist_ok=True)
			except:
				raise PermissionError(f"Could not create destination directory '{self.destination}' for package: {self.name}")

		initated_output = False
		for file in self.information['releases'][version]:
			target_architecture = False
			
			if file.get('python_version', None) == 'source':
				# We always accept the source code, as it can be compiled anywhere.
				target_architecture = True
			if file['filename'] == f"{self.name}-{version}.tar.gz":
				# We cannot reliably say that a straight up .tar.gz is NOT
				# the supported architecture and we'll have to include it.
				target_architecture = True
			else:
				for arch in storage['arguments'].architectures:
					if f"{arch.lower()}." in file['filename'].lower():
						target_architecture = True
						break

			if not target_architecture:
				log(f"  {file['filename']} not in target architectures: {storage['arguments'].architectures}", level=logging.DEBUG, fg="orange")
				continue

			if (self.destination/file['filename']).exists():
				with open(self.destination/file['filename'], 'rb') as fh:
					if hashlib.sha256(fh.read()).hexdigest() == file.get('digests', {}).get('sha256', None):
						log(f"  {file['filename']} (sha256 matched)", level=logging.DEBUG)
						continue
					elif hashlib.md5(fh.read()).hexdigest() == file.get('digests', {}).get('md5', None):
						log(f"  {file['filename']} (md5 matched)", level=logging.DEBUG)
						continue

			log(f"  Downloading: {file['filename']}", level=logging.INFO)
			log(f"  Sending request to {file['url']}", level=logging.DEBUG)

			if initated_output is False:
				log(f"Initating download of {self}@version: {version}", fg="yellow", level=logging.INFO)
				initated_output = True
				
			request = urllib.request.urlopen(urllib.request.Request(file['url'], headers={'User-Agent': f"python-pypiapi-{storage['version']}"}))

			try:
				with open(self.destination/file['filename'], "wb") as version_fh:
					version_fh.write(request.read())
			except urllib.error.URLError as err:
				(self.destination/file['filename']).unlink()
				log(f"Could not download {file['filename']} due to: {err}", level=logging.ERROR, fg="red")

		return True