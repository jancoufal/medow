import time
import datetime
from scrappers.util import formatters


class WebState(object):
	def __init__(self):
		self._start_time = datetime.datetime.now()
		self._int_count = 0

	def get_uptime(self):
		return formatters.ts_diff_to_str(self._start_time, datetime.datetime.now(), include_ms=False)

	def increment_counter(self):
		for _ in range(10):
			self._int_count += 1
			time.sleep(2)

	def get_int_count(self):
		return self._int_count
