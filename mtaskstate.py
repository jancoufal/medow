from dataclasses import dataclass
from enum import Enum
import datetime
from scrappers.util import formatters


class TaskStateEnum(Enum):
	QUEUED = "queued"
	RUNNING = "running"
	FINISHED = "finished"
	FAILED = "failed"


@dataclass
class TaskState(object):
	id: int
	state: TaskStateEnum
	name: str
	result: str
	start_time: datetime.datetime
	time_taken: str

	@property
	def age(self):
		return formatters.ts_diff_to_str(self.start_time, datetime.datetime.now(), False)
