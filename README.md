# python-pypiapi
Python library to interact with the pypi.org simple API defined in [PEP-503](https://www.python.org/dev/peps/pep-0503/).

# Usage

The following example filters out three libraries and download them one version at a time.<br>
This example relies on manually downloading each package, giving full control of how and when certain packages are downloaded.

```python
import pypiapi

for package in pypiapi.PackageListing({"archinstall" : True, "psycopg2" : True, "pypiapi" : True}):
	for version in package.versions():
		package.download(version, force=True)
```

The next example grabs the same packages, but does so fully automated and as efficiently as possible.

```python
import pypiapi

pypiapi.PackageListing({"archinstall" : True, "psycopg2" : True, "pypiapi" : True}).download()
```

Third and last example will download all available verions of all packages defined on pypi.org.<br>
The script also has to be called with `--retain-versions=''` to override the default 3-latest-versions policy.
```python
import pypiapi

pypiapi.PackageListing().download()
```

# Parameters/flags

`pypiapi` supports a couple of parameters independent of how you choose to script your downloads.<br>
These flags are as follows:

```
--mirror='pypi.org'
    Defines the hostname for the package database to sync from.
    pypi.org is the default value as it's the official URL for Python packages.

--port=443
    We default to port 443 and --tls as we prefer integrity checks.

--tls
    We default to port 443 and --tls.
    To turn it off, you need to do --tls='' to override tls.

--simple-api='/simple'
    This is the URL to the "simple api", aka directory listing of the packages.
    Each package needs to be wrapped in <a href="url">package name</a>\n for this lib to work.

--json-api='/pypi'
    This is the JSON api, we'll call this API endpoint followed by package name and /json.
    One example would be: /pypi/archinstall/json

--retain-versions=3
    How many versions of a package should we download/keep, given the --sort-algorithm used.
    This option can be overridden with --retain-versions='' but should generally not be to save
    some bandwidth of pypi.org but also yourself. Saves everyone a bunch of time to keep it default.

--sort-algorithm='LooseVersion'
    This tells us how to sort the version numbers. Since version naming convention isn't really
    strict, we default to LooseVersion which allows for version to end in a string, ex: 1.0b

--destination='./cache'
    Where to download the packages when we grab them.
    Each package will get its own folder under this destination.
    Ex: archinstall would be downloaded to ./cache/archinstall/archinstall-<version>.tar.gz

--timeout=5
    If the webserver timeouts on giving us the package listing (it can be quite large).
    This will tell the library how long to wait for more packages listing to be streamed to us.
    The default is 5 seconds, if we haven't recieved more package names by then, we abort.

--cache-listing
    `PackageListing()` in this library supports iterating over it, if iterated multiple times
    this flag will simply allow it to not fetch a new package listing again. It will cache
    whatever package names were given during initation, and the second iteration of `PackageListing()`
    will simply iterate over the cache instead. This speeds up the process quite a bit the second time around.

    Has to be overridden with --cache-listing='' if you wish to turn it off.

--py-versions=[3.0[,3.5]]
    This will download only packages that can meet the given version requirement.
    Default is to not filter out any supported versions and download all packages.

--licenses=[gpl[,mit]]
    Only packages that contain the given licensing short names will be downloaded.
    The default is to download all libraries/packages.

```