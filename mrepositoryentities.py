from dataclasses import dataclass
from datetime import datetime
from mformatters import Formatter, TimestampFormat


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

	@property
	def ts_start(self) -> str:
		return Formatter.NOT_AVAILABLE_STR if self.scrap_start is None else Formatter.ts_to_str(TimestampFormat.DATETIME, self.scrap_start)

	@property
	def ts_end(self) -> str:
		return Formatter.NOT_AVAILABLE_STR if self.scrap_end is None else Formatter.ts_to_str(TimestampFormat.DATETIME, self.scrap_end)

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
