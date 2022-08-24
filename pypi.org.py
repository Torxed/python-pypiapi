import json
import pypiapi

with open('/etc/proxy.conf') as proxy_conf:
	proxy = json.load(proxy_conf)

pypiapi.storage['arguments'].proxy_protocol = proxy['protocol']
pypiapi.storage['arguments'].proxy_host = proxy['address']
pypiapi.storage['arguments'].proxy_port = proxy['port']

pypiapi.storage['arguments'].retain_versions = 3
pypiapi.storage['arguments'].py_versions = '3'

packages = []
for package in pypiapi.PackageListing():
	print(package)

if pypiapi.storage['arguments'].retain_versions:
	for index in range(pypiapi.storage['arguments'].retain_versions):
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