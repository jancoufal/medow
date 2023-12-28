import time
import datetime
from scrappers.util import formatters
from mtaskresult import TaskResult
from typing import Dict


class WebState(object):
	def __init__(self):
		self._start_time = datetime.datetime.now()
		self._int_count = 0
		self._task_results = {}

	def get_uptime(self):
		return formatters.ts_diff_to_str(self._start_time, datetime.datetime.now(), include_ms=False)

	def increment_counter(self):
		for _ in range(2):
			self._int_count += 1
			time.sleep(2)

	def get_int_count(self):
		return self._int_count

	def update_task_result(self, task_result: TaskResult):
		self._task_results[task_result.id] = task_result

	def get_task_results(self) -> Dict[int, TaskResult]:
		return self._task_results
