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
		log(f"Retrieving raw package list", level=logging.DEBUG, fg="gray")
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

	@property
	def filter_packages(self):
		return {**self._filter_packages} if self._filter_packages else None
	
	def validate(self) -> bool:
		try:
			_package.load_information()
			return True
		except InvalidPackage:
			return False