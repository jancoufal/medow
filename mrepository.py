"""
persistent repository implementation
"""

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import List
from enum import Enum
from datetime import datetime
from msqlite_api import SqliteApi
from mscrapsources import ScrapSource
from mformatters import Formatter, TimestampFormat


class _Tables(Enum):
	SCRAP_STAT = "scrap_stat"
	SCRAP_FAILS = "scrap_fails"
	SCRAP_ITEMS = "scrap_items"


class _ScrapState(Enum):
	IN_PROGRESS = "in_progress"
	COMPLETE = "complete"
	FAILED = "failed"


class RepositoryInterface(ABCMeta):
	pass


@dataclass
class SourceScrapperItem:
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


@dataclass
class SourceScrapperScrap:
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
		return Formatter.NOT_AVAILABLE_STR if self.scrap_start is None else Formatter.ts_diff_to_str(self.scrap_start, datetime.now(),False)

	@property
	def time_taken(self) -> str:
		return Formatter.NOT_AVAILABLE_STR if None in (self.scrap_start, self.scrap_end) else Formatter.ts_diff_to_str(self.scrap_start, self.scrap_end, False)

	@property
	def success_percentage(self) -> str:
		return Formatter.percentage_str_safe(self.count_success, self.count_success + self.count_fail, Formatter.NOT_AVAILABLE_STR)


class RepositorySourceScrapper(object):
	def __init__(self, sqllite_api: SqliteApi, scrap_source: ScrapSource):
		super().__init__()
		self._sqllite_api = sqllite_api
		self._scrap_source = scrap_source

	def read_recent_items(self, item_limit: int) -> List[SourceScrapperItem]:
		def _row_mapper(r) -> SourceScrapperItem:
			return SourceScrapperItem(
				source=self._scrap_source.value,
				scrap_timestamp=Formatter.str_to_ts(TimestampFormat.DATETIME_MS, f"{r[0]} {r[1]}"),
				name=r[2],
				local_path=r[3],
				impressions=r[4]
			)

		stmt = f"""
			select ts_date, ts_time, name, local_path, impressions
			from {_Tables.SCRAP_ITEMS.value}
			inner join {_Tables.SCRAP_STAT.value}
				on {_Tables.SCRAP_STAT.value}.scrap_stat_id={_Tables.SCRAP_ITEMS.value}.scrap_stat_id
			where source=:source
			order by ts_date desc, ts_time desc
			limit :limit"""

		binds = {
			"source": self._scrap_source.value,
			"limit": item_limit
		}

		return self._sqllite_api.read(stmt, binds, _row_mapper)

	def read_recent_scraps(self, item_limit: int) -> List[SourceScrapperScrap]:
		def _row_mapper(r) -> SourceScrapperScrap:
			return SourceScrapperScrap(
				scrap_id=r[0],
				source=r[1],
				status=r[2],
				scrap_start=Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, f"{r[3]} {r[4]}", None),
				scrap_end=Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, f"{r[5]} {r[6]}", None),
				count_success=r[7],
				count_fail=r[8],
				exc_type=r[9],
				exc_value=r[10],
				exc_traceback=r[11],
			)

		stmt = f"""
			select
				{_Tables.SCRAP_STAT.value}_id,
				source,
				status,
				ts_start_date,
				ts_start_time,
				ts_end_date,
				ts_end_time,
				succ_count,
				fail_count,
				exc_type,
				exc_value,
				exc_traceback
			from {_Tables.SCRAP_STAT.value}
			order by {_Tables.SCRAP_STAT.value}_id desc
			limit :limit
			"""

		binds = {
			"limit": item_limit,
		}

		return self._sqllite_api.read(stmt, binds, _row_mapper)
