from dataclasses import dataclass
import datetime


@dataclass
class TaskResult(object):
	id: int
	name: str
	result: str
	is_error: bool
	start_time: datetime.datetime
	time_taken: str
