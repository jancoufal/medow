import datetime
from typing import Dict

from mtaskstate import TaskState
from scrappers.util import formatters


class WebState(object):
	def __init__(self):
		self._start_time = datetime.datetime.now()
		self._int_count = 0
		self._task_results = {}

	def get_uptime(self):
		return formatters.ts_diff_to_str(self._start_time, datetime.datetime.now(), include_ms=False)

	def update_task_state(self, task_result: TaskState):
		self._task_results[task_result.id] = task_result

	def get_task_states(self) -> Dict[int, TaskState]:
		return self._task_results
