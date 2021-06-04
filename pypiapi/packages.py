import copy
import socket
import ssl
import json
import logging
import pathlib
import urllib.request
import hashlib
import time

from .storage import storage
from .sockethelpers import epoll, EPOLLIN, EPOLLHUP
from .logger import log

class Package:
	def __init__(self, name):
		self._name = name
		self.cache = {}
		self.destination = None

	def __repr__(self):
		return f"Package(name={self.name})"

	@property
	def name(self):
		return self._name
	
	@property
	def information(self):
		self.set_destination()

		if not self.cache and self.destination.exists() is False:
			log(f"Sending request to https://{storage['arguments']['mirror']}{storage['arguments']['json-api']}/{self._name}/json", level=logging.DEBUG)
			request = urllib.request.urlopen(urllib.request.Request(f"https://{storage['arguments']['mirror']}{storage['arguments']['json-api']}/{self._name}/json", headers={'User-Agent': f"python-pypiapi-{storage['version']}"}))
			self.cache = json.loads(request.read().decode('UTF-8'))
		
		elif self.destination and self.destination.exists() and not self.cache:
			with open(f"{self.destination/self._name}.json", "r") as fh:
				self.cache = json.load(fh)
		
		elif self.destination and self.cache:
			if self.destination.exists() is False:
				self.destination.mkdir(parents=True, exist_ok=True)

			with open(f"{self.destination/self._name}.json", "w") as fh:
				json.dump(self.cache, fh)

		return self.cache

	@property
	def version(self):
		return self.information.get('info', {}).get('version', None)

	def set_destination(self, destination=None):
		if not destination:
			destination = storage['arguments']['destination']
		if type(destination) is str:
			destination = pathlib.Path(destination)

		destination = destination/self.name
		self.destination = destination

	def versions(self, limit=None):
		if not limit and storage['arguments']['retain-versions']:
			limit = int(storage['arguments']['retain-versions'])

		if storage['arguments']['sort-algorithm'] == 'LooseVersion':
			from distutils.version import LooseVersion
			versions = list(self.information.get('releases').keys())
			versions.sort(key=LooseVersion)
			versions.reverse()
			if not self.version in versions[:limit]:
				versions.insert(0, self.version)
			return versions[:limit]
		else:
			log(f"Unknown sorting algorithm: {storage['arguments']['sort-algorithm']}", level=logging.ERROR, fg="red")
			exit(1)

	def download(self, version, destination=None, threaded=False):
		self.set_destination(destination)

		if not self.information.get('releases', {}).get(version, None):
			raise KeyError(f"Package {self.name} does not have a version called: {version}")

		if not self.destination.exists():
			try:
				self.destination.mkdir(parents=True, exist_ok=True)
			except:
				raise PermissionError(f"Could not create destination directory '{self.destination}' for package: {self.name}")

		log(f"Processing {self}@version: {version}", fg="yellow", level=logging.INFO)
		for file in self.information['releases'][version]:
			if (self.destination/file['filename']).exists():
				with open(self.destination/file['filename'], 'rb') as fh:
					if hashlib.sha256(fh.read()).hexdigest() == file.get('digests', {}).get('sha256', None):
						log(f"  {file['filename']} (sha256 matched)", level=logging.DEBUG)
						continue
					elif hashlib.md5(fh.read()).hexdigest() == file.get('digests', {}).get('md5', None):
						log(f"  {file['filename']} (md5 matched)", level=logging.DEBUG)
						continue
			log(f"  Downloading: {file['filename']}", level=logging.INFO)

			log(f"Sending request to {file['url']}", level=logging.DEBUG)
			request = urllib.request.urlopen(urllib.request.Request(file['url'], headers={'User-Agent': f"python-pypiapi-{storage['version']}"}))

			with open(self.destination/file['filename'], "wb") as version_fh:
				version_fh.write(request.read())

class PackageListing:
	def __init__(self, filter_packages=None):
		self.socket = None
		self.pollobj = epoll()

		self.buffer = b''
		self.buffer_pos = 0
		self.headers = {}

		self._filter_packages = filter_packages

	def __iter__(self):
		if not storage['arguments']['cache-listing'] or len(self.buffer) == 0:
			if not self.socket:
				self.connect()

			if not self.headers:
				self.get_headers()

		filters = self.filter_packages

		last_data = time.time()
		while time.time() - last_data < storage['arguments']['timeout']:
			if self.socket:
				data = None
				for fileno, event in self.pollobj.poll(0.025):
					data = self.socket.recv(8192)
					last_data = time.time()
					break

				if data and len(data) == 0:
					return self.disconnect()
				elif data is None:
					continue

				self.buffer += data

			last_newline = self.buffer.rfind(b'\n')
			if storage['arguments']['cache-listing']:
				packages = self.buffer[self.buffer_pos:last_newline]
				self.buffer_pos = last_newline
			else:
				packages, self.buffer = self.buffer[:last_newline], self.buffer[last_newline:]

			for package in packages.split(b'\n'):
				if b'</html>' in package:
					break
				elif not b'<a' in package:
					# Warning: If they change from /simple/ then we're in trouble
					# This wasn't a package definition according to the /simple/ API
					continue

				package_url_start = package.find(b'href=')
				package_url_end = package.find(b'"', package_url_start+6)

				package_url = package[package_url_start+6:package_url_end].decode('UTF-8')
				package_name = pathlib.Path(package_url).name

				# TODO: Evaluate if getting the entire /simple/ listing and then filter packages
				#       is quicker or slower than attempting to grab HEAD on each package URL directly.
				#       If we have >100 packages filtered out, then perhaps getting the /simple/ list
				#       is quicker due to how HTTP calls natrually are slow in bulk, where as entire /simple/
				#       might just exhaust bandwidth once instead and be slow due to net-speeds.
				if filters:
					if package_name not in filters:
						continue
					del(filters[package_name])

				yield Package(package_name)

				if filters is not None and len(filters) == 0:
					break

			if filters is not None and len(filters) == 0:
				log(f"Recieved all packages requested in filter-list.", level=logging.INFO)
				break
			elif b'</html>' in package: # Package is a state variable from above, be wary about re-declaring it before this line
				break

		if time.time() - last_data >= storage['arguments']['timeout'] or b'</html>' in package:
			log(f"No more packages recieved from http(s)://{storage['arguments']['mirror']}:{int(storage['arguments']['port'])}{storage['arguments']['simple-api']}/", level=logging.WARNING, fg="yellow")

		self.disconnect()
		return None

	@property
	def filter_packages(self):
		return {**self._filter_packages} if self._filter_packages else None
	

	def connect(self):
		self.socket = socket.socket()
		self.socket.connect((storage['arguments']['mirror'], int(storage['arguments']['port'])))
		if storage['arguments']['tls']:
			context = ssl.create_default_context()
			self.socket = context.wrap_socket(self.socket, server_hostname=storage['arguments']['mirror'])

		self.pollobj.register(self.socket.fileno(), EPOLLIN | EPOLLHUP)

		self.GET(storage['arguments']['simple-api']+'/')

	def GET(self, url):
		if not self.socket:
			self.connect()

		header = f"GET {url} HTTP/1.1\r\n"
		header += f"Host: {storage['arguments']['mirror']}\r\n"
		header += f"User-Agent: python-pypiapi-{storage['version']}\r\n"
		header += "\r\n"

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

		log(f"Package listing is: {self.headers['content-length']} bytes")

	def download(self):
		for index in range(storage['arguments']['retain-versions']):
			for package in self:
				package.download(package.versions()[index])