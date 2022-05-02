import sys
import pathlib
import argparse
import logging
from .storage import *

__version__ = '0.0.1.dev2'

parser = argparse.ArgumentParser()
parser.add_argument("--mirror", default='pypi.org', type=str, nargs='?', help="Which upstream host contains the pypi API")
parser.add_argument("--port", default=443, type=int, nargs='?', help="Which port to connect to against the --mirror")
parser.add_argument("--tls", default=True, action="store_true", help="Enable TLS functionality against the API")
parser.add_argument("--simple-api", default='/simple', type=str, nargs='?', help="Which endpoint contains the simple API")
parser.add_argument("--json-api", default='/pypi', type=str, nargs='?', help="Which endpoint contains the JSON API")
parser.add_argument("--retain-versions", default=3, type=int, nargs='?', help="What is the global retension of versions per package")
parser.add_argument("--sort-algorithm", default='LooseVersion', type=str, nargs='?', help="Which version sort algorithm should be applied on --retain-versions")
parser.add_argument("--destination", default='./cache', type=pathlib.Path, nargs='?', help="Where should we place the package results")
parser.add_argument("--timeout", default=5, type=int, nargs='?', help="What global timeout should we have on trying to retrieve listings and packages")
parser.add_argument("--cache-listing", action="store_true", default=True, help="")
parser.add_argument("--py-versions", default='3', type=str, nargs='?', help="Which python versions of packages should we grab (default to only highest)")
parser.add_argument("--licenses", default='', type=str, nargs='?', help="Which licenses should we filter on, detaul any. Example: --licenses 'MIT,GPLv3'")
parser.add_argument("--architectures", default='x86_64,win_amd64,any', type=str, nargs='?', help="Which architectures (x86_64, i686, win32, win_amd64, etc) should we filter on, detaul any. Example: --licenses 'MIT,GPLv3'")
parser.add_argument("--verbosity-level", default='info', type=str, nargs='?', help="Sets the lowest threashold for log messages, according to https://docs.python.org/3/library/logging.html#logging-levels")
parser.add_argument("--paralell-downloads", default=2, type=int, nargs='?', help="Define how many paralell downloads can simulatniously be allowed to run.")

storage['arguments'], unknowns = parser.parse_known_args()
storage['version'] = __version__

storage['arguments'].destination = storage['arguments'].destination.resolve()
storage['arguments'].py_versions = [version for version in storage['arguments'].py_versions.split(',') if version]
storage['arguments'].licenses = [license for license in storage['arguments'].licenses.split(',') if license]
storage['arguments'].architectures = [arch for arch in storage['arguments'].architectures.split(',') if arch]

match storage['arguments'].verbosity_level.lower():
	case 'critical':
		storage['arguments'].verbosity_level = logging.CRITICAL
	case 'error':
		storage['arguments'].verbosity_level = logging.ERROR
	case 'warning':
		storage['arguments'].verbosity_level = logging.WARNING
	case 'info':
		storage['arguments'].verbosity_level = logging.INFO
	case 'debug':
		storage['arguments'].verbosity_level = logging.DEBUG
	case 'noset':
		storage['arguments'].verbosity_level = logging.NOSET
	

from .packages import *
from .sockethelpers import *