import json
import logging
import pypiapi
import asyncio

packages = {}

with open('/etc/proxy.conf') as proxy_conf:
	proxy = json.load(proxy_conf)

pypiapi.storage['arguments'].proxy_protocol = proxy['protocol']
pypiapi.storage['arguments'].proxy_host = proxy['address']
pypiapi.storage['arguments'].proxy_port = proxy['port']

pypiapi.storage['arguments'].retain_versions = 3
pypiapi.storage['arguments'].py_versions = '3'

async def get_packages(main_loop):
	for package in pypiapi.PackageListing():
		packages[package] = False

		if main_loop.is_running() is False:
			break

		await asyncio.sleep(0.025)

	pypiapi.log(f"Done listing all the packages", level=logging.INFO, fg="green")

async def download(listing_loop):
	while listing_loop.done() is False or len(list(packages.keys())) > 0:
		if pypiapi.storage['arguments'].retain_versions:
			for package in list(packages.keys()):
				if packages[package] is False:
					try:
						package.load_information()
					except pypiapi.InvalidPackage as err:
						pypiapi.log(f"Skipping package {package} due to: {err}", level=logging.WARNING, fg="orange")

						del(packages[package])
						continue

					packages[package] = True

				for index, version in enumerate(package.versions()):
					try:
						package.download(version)
					except pypiapi.DependencyError as err:
						pypiapi.log(f"Skipping package {package} due to: {err}", level=logging.WARNING, fg="orange")
						break
					except pypiapi.VersionError as err:
						pypiapi.log(f"Skipping package {package} due to: {err}", level=logging.WARNING, fg="orange")
						break

					if index == pypiapi.storage['arguments'].retain_versions - 1:
						break

				# Once we're on the final version, remove the package
				# To avoid iterating the package once more.
				# (Since download() is run until the listing is done)
				del(packages[package])

				await asyncio.sleep(0.0025)

		else:
			for package in list(packages.keys()):
				for version in package.versions():
					package.download(version)

		await asyncio.sleep(0.025)

if __name__ == '__main__':
	# loop = asyncio.get_event_loop()
	# listing = loop.create_task(get_packages(loop))
	# loop.run_until_complete(download(listing))
	loop = asyncio.get_event_loop()
	loop.run_until_complete(get_packages(loop))