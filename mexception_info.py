import sys, traceback


class ExceptionInfo(object):
	@classmethod
	def create_from_last_exception(cls):
		return cls(*sys.exc_info())

	def __init__(self, exception_type, value, trace_back):
		self._exception_type = exception_type
		self._value = value
		self._traceback = trace_back

	def __str__(self):
		return f"{self.exception_type=!s}, {self.value=!s}"

	@property
	def exception_type(self):
		return self._exception_type

	@property
	def value(self):
		return self._value

	@property
	def traceback(self):
		return self._traceback

	@property
	def formatted_exception(self):
		return traceback.format_exception(self.exception_type, value=self.value, tb=self.traceback)
