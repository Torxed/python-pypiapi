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
from distutils.version import LooseVersion
from typing import List

from .storage import storage
from .sockethelpers import epoll, EPOLLIN, EPOLLHUP
from .logger import log
from .licenses import licence_classifier_parser
from .exceptions import VersionError, DependencyError, YankedPackage, InvalidPackage
from .packages import Package

class PackageListing:
	def __init__(self, packages=None):
		self.socket = None
		self.pollobj = epoll()

		self.full_buffer = b''
		self.buffer = b''
		self.buffer_pos = 0
		self.expected_content_length = -1
		self.headers = {}

		self._packages = packages

		with urllib.request.urlopen('https://pypi.org/') as f:
			self.number_of_projects = int(re.findall('([0-9,.]+) (projects)', f.read().decode('utf-8'))[0][0].replace(',', '').replace('.', ''))

		log(f"Found that there should be {self.number_of_projects} number of projects", level=logging.INFO, fg="gray")

	def __iter__(self):
		with urllib.request.urlopen('https://pypi.org/simple/') as f:
			data = f.read()

		last_package_count_update = time.time()-10
		package_count = 0

		for line in data.split(b'\n'):
			if b'<a href=' in line:
				package_url_start = line.find(b'href=')
				package_url_end = line.find(b'"', package_url_start+6)

				package_url = line[package_url_start+6:package_url_end].decode('UTF-8')
				package_name = pathlib.Path(package_url).name

				package_count += 1
				package = Package(package_name)
				
				yield package

				if time.time() - last_package_count_update > 10:
					log(f"Processing package {package_count}/{self.number_of_projects} @ {package}", level=logging.INFO, fg="gray")
					last_package_count_update = time.time()


	# def __iter__(self):
	# 	if not storage['arguments'].cache_listing or len(self.buffer) == 0:
	# 		if not self.socket:
	# 			self.connect()

	# 		if not self.headers:
	# 			self.get_headers()

	# 	_packages = self._packages

	# 	log(f"Retrieving entire package listing content.", level=logging.INFO, fg="yellow")

	# 	last_data = time.time()

	# 	package_count = 0
	# 	last_package_count_update = time.time()-10
	# 	while time.time() - last_data < storage['arguments'].timeout:
	# 		if self.socket:
	# 			data = None
	# 			for fileno, event in self.pollobj.poll(0.025):
	# 				data = self.socket.recv(4096 * 4)
	# 				last_data = time.time()
	# 				break

	# 			if data and len(data) == 0:
	# 				return self.disconnect()
	# 			elif data is None:
	# 				continue

	# 			self.buffer += data
	# 			self.full_buffer += data

	# 		last_newline = self.buffer.rfind(b'\n')
	# 		if storage['arguments'].cache_listing:
	# 			packages = self.buffer[self.buffer_pos:last_newline]
	# 			self.buffer_pos = last_newline
	# 		else:
	# 			packages, self.buffer = self.buffer[:last_newline], self.buffer[last_newline:]

	# 		for package in packages.split(b'\n'):
	# 			if b'</html>' in package:
	# 				break
	# 			elif not b'<a' in package and len(package):
	# 				# Warning: If they change from /simple/ then we're in trouble
	# 				# This wasn't a package definition according to the /simple/ API
	# 				log(f"The following was not a /simple/ package definition: {package}", level=logging.WARNING, fg="orange")
	# 				continue

	# 			package_count += 1

	# 			package_url_start = package.find(b'href=')
	# 			package_url_end = package.find(b'"', package_url_start+6)

	# 			package_url = package[package_url_start+6:package_url_end].decode('UTF-8')
	# 			package_name = pathlib.Path(package_url).name

	# 			if time.time() - last_package_count_update > 10:
	# 				log(f"Processing package {package_count}/{self.number_of_projects} @ {package_name}", level=logging.INFO, fg="gray")
	# 				last_package_count_update = time.time()

	# 			# TODO: Evaluate if getting the entire /simple/ listing and then filter packages
	# 			#       is quicker or slower than attempting to grab HEAD on each package URL directly.
	# 			#       If we have >100 packages filtered out, then perhaps getting the /simple/ list
	# 			#       is quicker due to how HTTP calls natrually are slow in bulk, where as entire /simple/
	# 			#       might just exhaust bandwidth once instead and be slow due to net-speeds.
	# 			if _packages and package_name not in _packages:
	# 				continue
				
	# 				if type(_packages) == dict:
	# 					del(_packages[package_name])
	# 				else:
	# 					_packages.pop(_packages.index(package_name))

	# 			yield Package(package_name)

	# 			last_data = time.time()

	# 			if _packages is not None and len(_packages) == 0:
	# 				break

	# 		if _packages is not None and len(_packages) == 0:
	# 			log(f"Recieved all packages requested in filter-list.", level=logging.INFO)
	# 			break
	# 		elif b'</html>' in package: # Package is a state variable from above, be wary about re-declaring it before this line
	# 			break

	# 	if time.time() - last_data >= storage['arguments'].timeout or b'</html>' in package:
	# 		log(f"No more packages recieved from http(s)://{storage['arguments'].mirror}:{int(storage['arguments'].port)}{storage['arguments'].simple_api}/", level=logging.WARNING, fg="yellow")

	# 	if not self.expected_content_length == len(self.full_buffer):
	# 		log(f"Inconsistent data length on package listing, expected {self.expected_content_length} but got {len(self.full_buffer)}", level=logging.WARNING, fg="orange")

	# 	self.disconnect()
	# 	return None

	@property
	def filter_packages(self):
		return {**self._filter_packages} if self._filter_packages else None
	
	def validate(self) -> bool:
		try:
			_package.load_information()
			return True
		except InvalidPackage:
			return False

	def connect(self):
		self.socket = socket.socket()
		self.socket.connect((storage['arguments'].mirror, int(storage['arguments'].port)))
		if storage['arguments'].tls:
			context = ssl.create_default_context()
			self.socket = context.wrap_socket(self.socket, server_hostname=storage['arguments'].mirror)

		self.pollobj.register(self.socket.fileno(), EPOLLIN | EPOLLHUP)

		self.GET(storage['arguments'].simple_api+'/')

	def GET(self, url):
		if not self.socket:
			self.connect()

		header = f"GET {url} HTTP/1.1\r\n"
		header += f"Host: {storage['arguments'].mirror}\r\n"
		header += f"User-Agent: python-pypiapi-{storage['version']}\r\n"
		header += "\r\n"

		print(header)

		self.socket.send(bytes(header, 'UTF-8'))

	def disconnect(self):
		if self.socket:
			self.pollobj.unregister(self.socket.fileno())
			self.socket.close()
			self.socket = None
		self.buffer_pos = 0

	def get_headers(self):
		while True:
			data = None
			for fileno, event in self.pollobj.poll(0.025):
				data = self.socket.recv(8192)
				break

			if data and len(data) == 0:
				return self.disconnect()
			elif data is None:
				continue

			self.buffer += data

			if b'\r\n\r\n' in self.buffer:
				break

		header_data, self.buffer = self.buffer.split(b'\r\n\r\n', 1)
		for index, item in enumerate(header_data.split(b'\r\n')):
			if index == 0:
				self.headers['STATUS CODE'] = item.decode('UTF-8').split(' ')
			else:
				key, val = item.split(b':', 1)
				self.headers[key.strip().decode('UTF-8').lower()] = val.strip().decode('UTF-8')

		self.expected_content_length = int(self.headers['content-length'])
		log(f"Package listing is: {self.expected_content_length} bytes", level=logging.DEBUG, fg="yellow")

	def download(self):
		if storage['arguments'].retain_versions:
			for index in range(storage['arguments'].retain_versions):
				for package in self:
					if index >= len(package.versions()):
						continue
					try:
						package.download(package.versions()[index])
					except DependencyError as err:
						log(f"Skipping package {package} due to: {err}", level=logging.INFO, fg="yellow")
					except VersionError as err:
						log(f"Skipping package {package} due to: {err}", level=logging.INFO, fg="yellow")

		else:
			for package in self:
				for version in package.versions():
					package.download(version)