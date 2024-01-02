import datetime
import sqlite3
from enum import Enum
from pathlib import Path
from msource.sources import Source
from persistence.msqlite_api import SqliteApi
from mutil import formatters, exception_info


class _Tables(Enum):
	SCRAP_STAT = "scrap_stat"
	SCRAP_FAILS = "scrap_fails"
	SCRAP_ITEMS = "scrap_items"


class _ScrapState(Enum):
	IN_PROGRESS = "in_progress"
	COMPLETE = "complete"
	FAILED = "failed"


class Installer(object):
	@staticmethod
	def install(sql_connection: sqlite3.Connection):
		c = sql_connection.cursor()
		c.execute("""
			create table if not exists scrap_stat (
				scrap_stat_id integer primary key autoincrement,
				source text,
				ts_start_date text,
				ts_start_time text,
				ts_end_date text,
				ts_end_time text,
				status text,
				succ_count integer,
				fail_count integer
			);""")

		c.execute("""
			create table if not exists scrap_fails (
				scrap_fail_id integer primary key autoincrement,
				scrap_stat_id integer,
				ts_date text,
				ts_time text,
				item_name text,
				description text,
				exc_type text,
				exc_value text,
				exc_traceback text,
				foreign key(scrap_stat_id) references scrap_stat(scrap_stat_id)
			);	""")

		c.execute("""
			create table if not exists scrap_items(
				scrap_item_id integer primary key autoincrement,
				scrap_stat_id integer,
				ts_date text,
				ts_week text,
				ts_time text,
				local_path text,
				name text,
				impressions integer,
				foreign key(scrap_stat_id) references scrap_stat(scrap_stat_id)
			);	""")

		c.close()


class DbScrapWriter(object):
	@classmethod
	def create(cls, sqlite_datafile: Path, source: Source):
		return cls(SqliteApi(sqlite_datafile), source.value)

	def __init__(self, db_api: SqliteApi, source: str):
		self._db = db_api
		self._source = source
		self._scrap_stat_id = self._initialize_record()
		self._item_succ_count = 0
		self._item_fail_count = 0

	def _initialize_record(self):
		ts_now = datetime.datetime.now()
		self._db.write(_Tables.SCRAP_STAT.value, {
			"source": self._source,
			"ts_start_date": formatters.ts_to_str(formatters.TimestampFormat.DATE, ts_now),
			"ts_start_time": formatters.ts_to_str(formatters.TimestampFormat.TIME_MS, ts_now),
			"status": _ScrapState.IN_PROGRESS.value,
		})
		return self._db.read_last_seq(_Tables.SCRAP_STAT.value)

	def on_scrap_item_success(self, local_path: Path, item_name: str):
		self._item_succ_count += 1
		ts_now = datetime.datetime.now()
		self._db.write(_Tables.SCRAP_ITEMS.value, {
			"scrap_stat_id": self._scrap_stat_id,
			"ts_date": formatters.ts_to_str(formatters.TimestampFormat.DATE, ts_now),
			"ts_week": formatters.ts_to_str(formatters.TimestampFormat.WEEK, ts_now),
			"ts_time": formatters.ts_to_str(formatters.TimestampFormat.TIME_MS, ts_now),
			"local_path": str(local_path).replace("\\", "/"),
			"name": item_name,
			"impressions": 0,
		})

	def on_scrap_item_failure(self, item_name: str, description: str, exception_info: exception_info.ExceptionInfo):
		self._item_fail_count += 1
		ts_now = datetime.datetime.now()
		self._db.write(_Tables.SCRAP_FAILS.value, {
			"scrap_stat_id": self._scrap_stat_id,
			"ts_date": formatters.ts_to_str(formatters.TimestampFormat.DATE, ts_now),
			"ts_time": formatters.ts_to_str(formatters.TimestampFormat.TIME_MS, ts_now),
			"item_name": item_name,
			"description": description,
			"exc_type": str(exception_info.exception_type),
			"exc_value": str(exception_info.value),
			"exc_traceback": str(exception_info.formatted_exception),
		})

	def finish(self):
		ts_now = datetime.datetime.now()
		self._db.update(_Tables.SCRAP_STAT.value, {
			"ts_end_date": formatters.ts_to_str(formatters.TimestampFormat.DATE, ts_now),
			"ts_end_time": formatters.ts_to_str(formatters.TimestampFormat.TIME_MS, ts_now),
			"status": _ScrapState.COMPLETE.value,
			"succ_count": self._item_succ_count,
			"fail_count": self._item_fail_count,
		}, {
							"scrap_stat_id": self._scrap_stat_id,
						})

	def finish_exceptionally(self, exception_info: exception_info.ExceptionInfo):
		ts_now = datetime.datetime.now()
		self._db.update(_Tables.SCRAP_STAT.value, {
			"ts_end_date": formatters.ts_to_str(formatters.TimestampFormat.DATE, ts_now),
			"ts_end_time": formatters.ts_to_str(formatters.TimestampFormat.TIME_MS, ts_now),
			"status": _ScrapState.FAILED.value,
			"succ_count": self._item_succ_count,
			"fail_count": self._item_fail_count,
			"exc_type": str(exception_info.exception_type),
			"exc_value": str(exception_info.value),
			"exc_traceback": str(exception_info.formatted_exception),
		}, {
							"scrap_stat_id": self._scrap_stat_id,
						})


class DbScrapReader(object):
	@classmethod
	def create(cls, sqlite_datafile: Path, source: Source):
		return cls(SqliteApi(sqlite_datafile), source.value)

	def __init__(self, db_api: SqliteApi, source: str):
		self._db = db_api
		self._source = source

	def read_recent_items(self, item_limit: int):
		def _row_mapper(r):
			scrap_ts = formatters.str_to_ts(formatters.TimestampFormat.DATETIME_MS, f"{r[0]} {r[1]}")
			return {
				"datetime": formatters.ts_to_str(formatters.TimestampFormat.DATETIME, scrap_ts),
				"age": formatters.ts_diff_to_str(scrap_ts, datetime.datetime.now(), False),
				"name": r[2],
				"local_path": r[3],
				"impressions": r[4],
			}

		stmt = f"""
			select ts_date, ts_time, name, local_path, impressions
			from {_Tables.SCRAP_ITEMS.value}
			inner join {_Tables.SCRAP_STAT.value}
				on {_Tables.SCRAP_STAT.value}.scrap_stat_id={_Tables.SCRAP_ITEMS.value}.scrap_stat_id
			where source=:source
			order by ts_date desc, ts_time desc
			limit :limit"""

		binds = {
			"source": self._source,
			"limit": SqliteApi.clamp_limit(item_limit)
		}

		return self._db.read(stmt, binds, _row_mapper)

	def read_recent_item_names(self):
		stmt = f"""
			select distinct name
			from {_Tables.SCRAP_ITEMS.value}
			inner join {_Tables.SCRAP_STAT.value}
				on {_Tables.SCRAP_STAT.value}.scrap_stat_id={_Tables.SCRAP_ITEMS.value}.scrap_stat_id
			where source=:source and scrap_items.ts_date > date('now', '-6 month')
			"""

		binds = {
			"source": self._source,
		}

		return self._db.read(stmt, binds, lambda r: r[0])


class DbStatReader(object):
	@classmethod
	def create(cls, sqlite_datafile: Path):
		return cls(SqliteApi(sqlite_datafile))

	def __init__(self, db_api: SqliteApi):
		self._db = db_api

	def read_last_scraps(self, record_limit: int):
		def _to_ts_safe(date_string, time_string):
			try:
				return formatters.str_to_ts(formatters.TimestampFormat.DATETIME_MS, f"{date_string} {time_string}")
			except:
				return None

		def _percent_str_safe(succ_count, fail_count):
			try:
				return formatters.percentage_str(succ_count, succ_count + fail_count)
			except:
				return formatters.NOT_AVAILABLE_STR

		def _mapper(row):
			scrap_s = _to_ts_safe(*row[3:5])
			scrap_e = _to_ts_safe(*row[5:7])
			return {
				"scrap_id": row[0],
				"source": row[1],
				"status": row[2],
				"ts_start": formatters.NOT_AVAILABLE_STR if scrap_s is None else formatters.ts_to_str(
					formatters.TimestampFormat.DATETIME, scrap_s),
				"ts_end": formatters.NOT_AVAILABLE_STR if scrap_e is None else formatters.ts_to_str(
					formatters.TimestampFormat.DATETIME, scrap_e),
				"age": formatters.NOT_AVAILABLE_STR if scrap_s is None else formatters.ts_diff_to_str(
					scrap_s,
					datetime.datetime.now(),
					False),
				"time_taken": formatters.NOT_AVAILABLE_STR if None in (scrap_s, scrap_e) else formatters.ts_diff_to_str(
					scrap_s, scrap_e, False),
				"count_succ": row[7],
				"count_fail": row[8],
				"succ_percentage": _percent_str_safe(row[7], row[8]),
				"exc_type": row[9],
				"exc_value": row[10],
				"exc_traceback": row[11],
			}

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
			"limit": SqliteApi.clamp_limit(record_limit),
		}

		return self._db.read(stmt, binds, _mapper)
