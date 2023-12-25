import typing
import sqlite3
import datetime
import enum
import pathlib
from ..util import exception_info, formatters
from ..sources import Source


class _Tables(enum.Enum):
	SCRAP_STAT = "scrap_stat"
	SCRAP_FAILS = "scrap_fails"
	SCRAP_ITEMS = "scrap_items"


class _ScrapState(enum.Enum):
	IN_PROGRESS = "in_progress"
	COMPLETE = "complete"
	FAILED = "failed"


class _SqliteApi(object):

	SELECT_LIMIT_MIN = 1
	SELECT_LIMIT_MAX = 300
	SELECT_LIMIT_FALLBACK = 10

	def __init__(self, sqlite_datafile:pathlib.Path):
		self.sqlite_datafile = sqlite_datafile

	@staticmethod
	def clamp_limit(limit_value:int):
		if not isinstance(limit_value, int):
			return _SqliteApi.SELECT_LIMIT_FALLBACK
		
		if limit_value < _SqliteApi.SELECT_LIMIT_MIN:
			return _SqliteApi.SELECT_LIMIT_MIN

		if limit_value > _SqliteApi.SELECT_LIMIT_MAX:
			return _SqliteApi.SELECT_LIMIT_MAX

		return limit_value

	def do_with_connection(self, connection_cb:callable):
		db_conn = sqlite3.Connection(self.sqlite_datafile)
		try:
			with db_conn:
				return connection_cb(db_conn)
		finally:
			db_conn.close()

	def do_with_cursor(self, cursor_cb:callable):
		def _cursor_call(connection):
			db_cursor = connection.cursor()
			try:
				cb_result = cursor_cb(db_cursor)
				connection.commit()
				return cb_result
			finally:
				db_cursor.close()

		return self.do_with_connection(_cursor_call)

	def read(self, sql_stmt:str, binds, row_mapper:callable=None):
		def _reader(cursor):
			r_mapper = row_mapper if row_mapper is not None else lambda row: row
			result = list()
			for r in cursor.execute(sql_stmt, binds):
				result.append(r_mapper(r))
			return result

		return self.do_with_cursor(_reader)

	def compose_and_read(self, source_table:str, joins: str, column_list:list, filter_map:dict, order_tuple_list:tuple, limit:int, row_mapper:callable=None):
		stmt = f"select {', '.join(column_list)} from {source_table}"

		if joins is not None:
			stmt += " " + joins

		if filter_map is not None and len(filter_map) > 0:
			stmt += " where " + " and ".join(f"{k}=:{k}" for k in filter_map.keys())

		if order_tuple_list is not None and len(order_tuple_list) > 0:
			stmt += " order by " + ", ".join(f"{_1} {_2}" for (_1, _2) in order_tuple_list)

		stmt += " limit " + str(_SqliteApi.clamp_limit(limit))

		return self.read(stmt, filter_map)

	def write(self, table_name, value_mapping:dict):
		def _writer(connection):
			cols = list(value_mapping.keys())
			sql_stmt = f"insert into {table_name}({', '.join(cols)}) values (:{', :'.join(cols)})"
			connection.execute(sql_stmt, value_mapping)

		return self.do_with_connection(_writer)

	def update(self, table_name, value_mapping:dict, where_condition_mapping:dict):
		def _writer(connection):
			# rename all value_mapping keys to "new_{key}" and where_condition_mapping keys to "where_{key}"
			# statement pattern:
			# update table_name set col_a=:new_col_a, col_b=:new_col_b where col_c=:where_col_c and col_d=:where_col_d
			stmt_set = ", ".join(map(lambda k: f"{k}=:new_{k}", value_mapping.keys()))
			stmt_whr = " and ".join(map(lambda k: f"{k}=:where_{k}", where_condition_mapping.keys()))
			sql_stmt = f"update {table_name} set {stmt_set} where {stmt_whr}"
			connection.execute(sql_stmt, {
				**{ f"new_{k}": v for (k, v) in value_mapping.items() },
				**{ f"where_{k}": v for (k, v) in where_condition_mapping.items() }
			})

		return self.do_with_connection(_writer)

	def read_last_seq(self, table_name):
		def _reader(cursor):
			cursor.execute("select seq from sqlite_sequence where name=?", (table_name, ))
			return cursor.fetchone()[0]

		return self.do_with_cursor(_reader)


class DbScrapWriter(object):
	@classmethod
	def create(cls, sqlite_datafile:pathlib.Path, source:Source):
		return cls(_SqliteApi(sqlite_datafile), source.value)

	def __init__(self, db_api:_SqliteApi, source:str):
		self._db = db_api
		self._source = source
		self._scrap_stat_id = self._initialize_record()
		self._item_succ_count = 0
		self._item_fail_count = 0

	def _initialize_record(self):
		ts_now = datetime.datetime.now()
		self._db.write(_Tables.SCRAP_STAT.value, {
			"source": self._source,
			"ts_start_date": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.DATE, ts_now),
			"ts_start_time": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.TIME_MS, ts_now),
			"status": _ScrapState.IN_PROGRESS.value,
		})
		return self._db.read_last_seq(_Tables.SCRAP_STAT.value)

	def on_scrap_item_success(self, local_path:pathlib.Path, item_name:str):
		self._item_succ_count += 1
		ts_now = datetime.datetime.now()
		self._db.write(_Tables.SCRAP_ITEMS.value, {
			"scrap_stat_id": self._scrap_stat_id,
			"ts_date": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.DATE, ts_now),
			"ts_week": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.WEEK, ts_now),
			"ts_time": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.TIME_MS, ts_now),
			"local_path": str(local_path).replace("\\", "/"),
			"name": item_name,
			"impressions": 0,
		})

	def on_scrap_item_failure(self, item_name:str, description:str, exception_info:exception_info.ExceptionInfo):
		self._item_fail_count += 1
		ts_now = datetime.datetime.now()
		self._db.write(_Tables.SCRAP_FAILS.value, {
			"scrap_stat_id": self._scrap_stat_id,
			"ts_date": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.DATE, ts_now),
			"ts_time": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.TIME_MS, ts_now),
			"item_name": item_name,
			"description": description,
			"exc_type": str(exception_info.exception_type),
			"exc_value": str(exception_info.value),
			"exc_traceback": str(exception_info.formatted_exception),
		})

	def finish(self):
		ts_now = datetime.datetime.now()
		self._db.update(_Tables.SCRAP_STAT.value, {
			"ts_end_date": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.DATE, ts_now),
			"ts_end_time": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.TIME_MS, ts_now),
			"status": _ScrapState.COMPLETE.value,
			"succ_count": self._item_succ_count,
			"fail_count": self._item_fail_count,
		}, {
			"scrap_stat_id": self._scrap_stat_id,
		})

	def finish_exceptionaly(self, exception_info:exception_info.ExceptionInfo):
		ts_now = datetime.datetime.now()
		self._db.update(_Tables.SCRAP_STAT.value, {
			"ts_end_date": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.DATE, ts_now),
			"ts_end_time": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.TIME_MS, ts_now),
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
	def create(cls, sqlite_datafile:pathlib.Path, source:Source):
		return cls(_SqliteApi(sqlite_datafile), source.value)

	def __init__(self, db_api:_SqliteApi, source:str):
		self._db = db_api
		self._source = source

	def read_recent_items(self, item_limit:int):
		def _row_mapper(r):
			scrap_ts = formatters.str_to_ts(formatters.TIMESTAMP_FORMAT.DATETIME_MS, f"{r[0]} {r[1]}")
			return {
				"datetime": formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.DATETIME, scrap_ts),
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
			"limit": _SqliteApi.clamp_limit(item_limit)
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
	def create(cls, sqlite_datafile:pathlib.Path):
		return cls(_SqliteApi(sqlite_datafile))

	def __init__(self, db_api:_SqliteApi):
		self._db = db_api

	def read_last_scraps(self, record_limit:int):
		def _to_ts_safe(date_string, time_string):
			try:
				return formatters.str_to_ts(formatters.TIMESTAMP_FORMAT.DATETIME_MS, f"{date_string} {time_string}")
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
				"ts_start": formatters.NOT_AVAILABLE_STR if scrap_s is None else formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.DATETIME, scrap_s),
				"ts_end": formatters.NOT_AVAILABLE_STR if scrap_e is None else formatters.ts_to_str(formatters.TIMESTAMP_FORMAT.DATETIME, scrap_e),
				"age": formatters.NOT_AVAILABLE_STR if scrap_s is None else formatters.ts_diff_to_str(scrap_s, datetime.datetime.now(), False),
				"time_taken": formatters.NOT_AVAILABLE_STR if None in (scrap_s, scrap_e) else formatters.ts_diff_to_str(scrap_s, scrap_e, False),
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
			"limit": _SqliteApi.clamp_limit(record_limit),
		}

		return self._db.read(stmt, binds, _mapper)
		
