class DependencyError(BaseException):
	pass

class VersionError(BaseException):
	pass

class YankedPackage(BaseException):
	pass

class InvalidPackage(BaseException):
	pass