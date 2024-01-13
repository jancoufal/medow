from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from mformatters import Formatter, TimestampFormat


class TaskStatusEnum(Enum):
	CREATED = "created"
	RUNNING = "running"
	COMPLETED = "completed"
	ERROR = "error"


@dataclass
class MScrapTaskE:
	pk_id: int | None
	scrapper: str
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


@dataclass
class MScrapTaskItemE:
	pk_id: int | None
	task_id: int
	ts_start: str
	ts_end: str | None
	status: str
	item_name: str
	local_path: str | None
	exception_type: str | None
	exception_value: str | None

	@property
	def start_as_timestamp(self) -> datetime | None:
		return Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, self.ts_start, None)

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


# TODO: remove
"""
@dataclass
class ScrapStatEntity:
	scrap_id: int
	source: str
	status: str
	scrap_start: datetime | None
	scrap_end: datetime | None
	count_success: int
	count_fail: int
	exc_type: str | None
	exc_value: str | None
	exc_traceback: str | None

	@staticmethod
	def _format_ts(dt: datetime, formatter: TimestampFormat) -> str:
		return Formatter.ts_to_str(formatter, dt) if dt is not None else Formatter.NOT_AVAILABLE_STR

	@property
	def ts_start(self) -> str:
		return ScrapStatEntity._format_ts(self.scrap_start, TimestampFormat.DATETIME)

	@property
	def ts_start_week(self) -> str:
		return ScrapStatEntity._format_ts(self.scrap_start, TimestampFormat.WEEK)

	@property
	def ts_start_date_and_time(self) -> tuple[str, str]:
		d = ScrapStatEntity._format_ts(self.scrap_start, TimestampFormat.DATE)
		t = ScrapStatEntity._format_ts(self.scrap_start, TimestampFormat.TIME)
		return d, t

	@property
	def ts_end(self) -> str:
		return ScrapStatEntity._format_ts(self.scrap_end, TimestampFormat.DATETIME)

	@property
	def ts_end_date_and_time(self) -> tuple[str, str]:
		d = ScrapStatEntity._format_ts(self.scrap_end, TimestampFormat.DATE)
		t = ScrapStatEntity._format_ts(self.scrap_end, TimestampFormat.TIME)
		return d, t

	@property
	def age(self) -> str:
		return Formatter.NOT_AVAILABLE_STR if self.scrap_start is None else Formatter.ts_diff_to_str(self.scrap_start, datetime.now(), False)

	@property
	def time_taken(self) -> str:
		return Formatter.NOT_AVAILABLE_STR if None in (self.scrap_start, self.scrap_end) else Formatter.ts_diff_to_str(self.scrap_start, self.scrap_end, False)

	@property
	def success_percentage(self) -> str:
		return Formatter.percentage_str_safe(self.count_success, self.count_success + self.count_fail, Formatter.NOT_AVAILABLE_STR)


@dataclass
class ScrapItemEntity:
	source: str
	scrap_timestamp: datetime
	name: str
	local_path: str
	impressions: int

	@property
	def age(self) -> str:
		return Formatter.ts_diff_to_str(self.scrap_timestamp, datetime.now(), False)

	@property
	def scrap_timestamp_str(self):
		return Formatter.ts_to_str(TimestampFormat.DATETIME)
"""