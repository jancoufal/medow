from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from mformatters import Formatter, TimestampFormat


class TaskClass(Enum):
	DUMMY = "dummy"
	SCRAP = "scrap"
	SYNC = "sync"


class TaskType(Enum):
	DUMMY = "dummy"
	ROUMEN_KECY = "roumen_kecy"
	ROUMEN_MASO = "roumen_maso"
	YOUTUBE_DL = "youtube_dl"


@dataclass
class TaskClassAndType:
	cls: TaskClass
	typ: TaskType

	def __str__(self) -> str:
		return f"{self.cls.value}.{self.typ.value}"


class TaskStatusEnum(Enum):
	CREATED = "created"
	RUNNING = "running"
	COMPLETED = "completed"
	ERROR = "error"


class TaskSyncStatusEnum(Enum):
	IGNORE = "ignore"
	NOT_SYNCED = "not_synced"
	SYNCED = "synced"


@dataclass
class MTaskE:
	pk_id: int | None
	task_class: str
	task_type: str
	ts_start: str
	ts_end: str | None
	status: str
	item_count_success: int
	item_count_fail: int
	exception_type: str | None
	exception_value: str | None

	@property
	def start_as_timestamp(self) -> datetime | None:
		return Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, self.ts_start, None)

	@property
	def start_date(self) -> datetime | None:
		return Formatter.ts_to_str(TimestampFormat.DATETIME, self.start_as_timestamp)

	@property
	def end_as_timestamp(self) -> datetime | None:
		return Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, self.ts_end, None)

	@property
	def age(self) -> str:
		s = self.start_as_timestamp
		return Formatter.NOT_AVAILABLE_STR if s is None else Formatter.ts_diff_to_str(s, datetime.now(), False)

	@property
	def time_taken(self) -> str:
		s, e = self.start_as_timestamp, self.end_as_timestamp
		return Formatter.NOT_AVAILABLE_STR if None in (s, e) else Formatter.ts_diff_to_str(s, e, False)

	@property
	def success_percentage(self) -> str:
		s, f = self.item_count_success, self.item_count_fail
		return Formatter.percentage_str_safe(s, s+f, Formatter.NOT_AVAILABLE_STR)

	@property
	def task_def_html(self):
		task_class_mapper = {
			TaskClass.DUMMY.value: ".",
			TaskClass.SCRAP.value: "&#x21ca;",  # two arrows down
			TaskClass.SYNC.value: "&#x21c8;",  # two arrows up
		}
		task_type_mapper = {
			TaskType.DUMMY.value: ".",
			TaskType.ROUMEN_KECY.value: "rk",
			TaskType.ROUMEN_MASO.value: "rm",
			TaskType.YOUTUBE_DL.value: "yt",
		}
		return task_class_mapper.get(self.task_class, "?") + "/" + task_type_mapper.get(self.task_type, "?")


@dataclass
class MTaskItemE:
	pk_id: int | None
	ref_id: int | None
	task_id: int
	ts_start: str
	ts_end: str | None
	status: str
	item_name: str
	destination_path: str | None
	exception_type: str | None
	exception_value: str | None
	sync_status: str

	@property
	def start_as_timestamp(self) -> datetime | None:
		return Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, self.ts_start, None)

	@property
	def start_date(self) -> datetime | None:
		return Formatter.ts_to_str(TimestampFormat.DATETIME, self.start_as_timestamp)

	@property
	def end_as_timestamp(self) -> datetime | None:
		return Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, self.ts_end, None)

	@property
	def age(self) -> str:
		s = self.start_as_timestamp
		return Formatter.NOT_AVAILABLE_STR if s is None else Formatter.ts_diff_to_str(s, datetime.now(), False)

	@property
	def time_taken(self) -> str:
		s, e = self.start_as_timestamp, self.end_as_timestamp
		return Formatter.NOT_AVAILABLE_STR if None in (s, e) else Formatter.ts_diff_to_str(s, e, False)
