import sys
import pathlib

__version__ = '0.0.1.dev1'

## Basic version of arg.parse() supporting:
##  --key=value
##  --boolean
arguments = {}
positionals = []

# Setup some sane defaults
arguments['mirror'] = 'pypi.org'
arguments['port'] = 443
arguments['tls'] = True
arguments['simple-api'] = '/simple'
arguments['json-api'] = '/pypi'
# TDB: arguments['projects'] = 'archinstall,psycopg2'
arguments['retain-versions'] = 3
arguments['sort-algorithm'] = 'LooseVersion'
# TBD: arguments['paralell'] = arguments['retain-versions'] * arguments['retain-versions'] # Allow 3 projects simultaniously
# TBD: arguments['one-version-increments'] = True # Always download the latest version and come back for older later
arguments['destination'] = './cache'
arguments['timeout'] = 5
arguments['cache-listing'] = True
# Filters (only grabs packages that support these filters):
arguments['py-versions'] = ''
arguments['licenses'] = ''

for arg in sys.argv[1:]:
	if '--' == arg[:2]:
		if '=' in arg:
			key, val = [x.strip() for x in arg[2:].split('=', 1)]
		else:
			key, val = arg[2:], True
		arguments[key] = val
	else:
		positionals.append(arg)

from .storage import *
storage['arguments'] = arguments
storage['version'] = __version__
arguments['destination'] = pathlib.Path(arguments['destination'])
arguments['py-versions'] = [version for version in arguments['py-versions'].split(',') if version]
arguments['licenses'] = [license for license in arguments['licenses'].split(',') if license]

from .packages import *
from .sockethelpers import *