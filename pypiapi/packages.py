import socket
import ssl
import logging
import pathlib

from .storage import storage
from .sockethelpers import epoll, EPOLLIN, EPOLLHUP
from .logger import log

class PackageListing:
	def __init__(self):
		self.socket = None
		self.pollobj = epoll()

		self.buffer = b''
		self.headers = {}

	def __iter__(self):
		if not self.socket:
			self.connect()

		if not self.headers:
			self.get_headers()

		# Warning
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

			last_newline = self.buffer.rfind(b'\n')
			packages, self.buffer = self.buffer[:last_newline], self.buffer[last_newline:]

			for package in packages.split(b'\n'):
				if not b'<a' in package:
					# Warning: If they change from /simple/ then we're in trouble
					# This wasn't a package definition according to the /simple/ API
					continue

				package_url_start = package.find(b'href=')
				package_url_end = package.find(b'"', package_url_start+6)

				package_url = package[package_url_start+6:package_url_end].decode('UTF-8')
				package_name = pathlib.Path(package_url).name

				yield {'name' : package_name, 'url' : package_url}

			break

		"""
		<body>
			<a href="/simple/0/">0</a>
			<a href="/simple/0rss/">0rss</a>
			...
		</body>
		"""

	def connect(self):
		self.socket = socket.socket()
		self.socket.connect((storage['arguments']['mirror'], int(storage['arguments']['port'])))
		if storage['arguments']['tls']:
			context = ssl.create_default_context()
			self.socket = context.wrap_socket(self.socket, server_hostname=storage['arguments']['mirror'])

		self.pollobj.register(self.socket.fileno(), EPOLLIN | EPOLLHUP)

		self.GET(storage['arguments']['api-endpoint']+'/')

	def GET(self, url):
		if not self.socket:
			self.connect()

		header = f"GET {url} HTTP/1.1\r\n"
		header += f"Host: {storage['arguments']['mirror']}\r\n"
		header += f"User-Agent: python-pypiapi-{storage['version']}\r\n"
		header += "\r\n"

		self.socket.send(bytes(header, 'UTF-8'))

	def disconnect(self):
		self.pollobj.unregister(self.socket.fileno())
		self.socket.close()
		self.socket = None

	def get_headers(self):
		# Warning
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
			print(self.buffer.decode('UTF-8'))

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