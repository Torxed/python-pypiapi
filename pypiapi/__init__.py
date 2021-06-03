import sys

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
arguments['api-endpoint'] = '/simple'
arguments['projects'] = 'archinstall,psycopg2'
arguments['retain-versions'] = 3
arguments['sort-algorithm'] = 'version'
arguments['paralell'] = arguments['retain-versions'] * arguments['retain-versions'] # Allow 3 projects simultaniously
arguments['one-version-increments'] = True # Always download the latest version and come back for older later


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
from .packages import *
from .sockethelpers import *