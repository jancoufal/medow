"""
persistent repository implementation
"""

import sqlite3
from abc import ABCMeta
from dataclasses import asdict
from enum import Enum
from typing import List

from mrepositoryentities import *
from mscrapsources import ScrapSource
from msqlite_api import SqliteApi


class _Tables(Enum):
	SCRAP_TASK = "scrap_task"
	SCRAP_TASK_ITEM = "scrap_task_item"


class _ScrapState(Enum):
	IN_PROGRESS = "in_progress"
	COMPLETE = "complete"
	FAILED = "failed"


class RepositoryInterface(ABCMeta):
	pass


class Repository(object):
	def __init__(self, sqlite_api: SqliteApi):
		super().__init__()
		self._sqlite_api = sqlite_api

	@staticmethod
	def _get_entity_table(entity: MScrapTaskE | MScrapTaskItemE) -> str:
		match entity:
			case MScrapTaskE(): return "scrap_task"
			case MScrapTaskItemE(): return "scrap_task_item"
			case _: raise ValueError(f"Unknown entity {entity}.")

	def save_entity(self, entity: MScrapTaskE | MScrapTaskItemE, get_last_id: bool):
		table_name = Repository._get_entity_table(entity)
		entity_as_dict = asdict(entity)
		col_names = ",".join(entity_as_dict.keys())
		bind_names = ",".join((":" + c for c in entity_as_dict.keys()))
		stmt = f"INSERT INTO {table_name}({col_names}) values ({bind_names})"

		def _exec_without_id_return(con: sqlite3.Connection):
			con.execute(stmt, entity_as_dict)
			con.commit()
			return None

		def _exec_with_id_return(cur: sqlite3.Cursor):
			cur.execute(stmt, entity_as_dict)
			last_id = cur.lastrowid
			cur.connection.commit()
			return last_id

		if get_last_id:
			return self._sqlite_api.do_with_cursor(_exec_with_id_return)
		else:
			return self._sqlite_api.do_with_connection(_exec_without_id_return)

	def update_entity(self, entity: MScrapTaskE | MScrapTaskItemE):
		def _updater(conn: sqlite3.Connection):
			# rename all value_mapping keys to "new_{key}" and where_condition_mapping keys to "where_{key}"
			# statement pattern:
			# update table_name set col_a=:new_col_a, col_b=:new_col_b where col_c=:where_col_c and col_d=:where_col_d
			table_name = Repository._get_entity_table(entity)
			entity_as_dict = asdict(entity)
			stmt_set = ", ".join(map(lambda k: f"{k}=:new_{k}", entity_as_dict.keys()))
			stmt_whr = {
				**{f"new_{k}": v for (k, v) in entity_as_dict.items()},
				**{"whr_pk_id": entity.pk_id}
			}
			stmt = f"update {table_name} set {stmt_set} where pk_id=:whr_pk_id"
			conn.execute(stmt, stmt_whr)
		self._sqlite_api.do_with_connection(_updater)

	def load_entity_scrap_task(self, pk_id: int) -> MScrapTaskE | None:
		return self._sqlite_api.read(
			f"select * from {_Tables.SCRAP_TASK.value} where pk_id=:pk_id",
			{"pk_id": pk_id},
			lambda rs: MScrapTaskE(*rs)
		).pop()

	def read_recent_scrap_tasks(self, scrap_source: ScrapSource, item_limit: int) -> List[MScrapTaskE]:
		stmt = f"select * from {_Tables.SCRAP_TASK.value} where scrapper=:scrapper order by pk_id desc limit :limit"

		binds = {
			"scrapper": scrap_source.value,
			"limit": item_limit,
		}

		return self._sqlite_api.read(stmt, binds, lambda rs: MScrapTaskE(*rs))


class RepositorySourceScrapper(object):
	def __init__(self, sqlite_api: SqliteApi, scrap_source: ScrapSource):
		super().__init__()
		self._sqlite_api = sqlite_api
		self._scrap_source = scrap_source

	# def read_recent_scraps(self, item_limit: int) -> List[MScrapTaskE]:
	# 	def _row_mapper(r) -> ScrapStatEntity:
	# 		return ScrapStatEntity(
	# 			scrap_id=r[0],
	# 			source=r[1],
	# 			status=r[2],
	# 			scrap_start=Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, f"{r[3]} {r[4]}", None),
	# 			scrap_end=Formatter.str_to_ts_safe(TimestampFormat.DATETIME_MS, f"{r[5]} {r[6]}", None),
	# 			count_success=r[7],
	# 			count_fail=r[8],
	# 			exc_type=r[9],
	# 			exc_value=r[10],
	# 			exc_traceback=r[11],
	# 		)
	#
	# 	stmt = f"""
	# 		select
	# 			{_Tables.SCRAP_STAT.value}_id,
	# 			source,
	# 			status,
	# 			ts_start_date,
	# 			ts_start_time,
	# 			ts_end_date,
	# 			ts_end_time,
	# 			succ_count,
	# 			fail_count,
	# 			exc_type,
	# 			exc_value,
	# 			exc_traceback
	# 		from {_Tables.SCRAP_STAT.value}
	# 		order by {_Tables.SCRAP_STAT.value}_id desc
	# 		limit :limit
	# 		"""
	#
	# 	binds = {
	# 		"limit": item_limit,
	# 	}
	#
	# 	return self._sqlite_api.read(stmt, binds, _row_mapper)
	#
	# def read_recent_items(self, item_limit: int) -> List[ScrapItemEntity]:
	# 	def _row_mapper(r) -> ScrapItemEntity:
	# 		return ScrapItemEntity(
	# 			source=self._scrap_source.value,
	# 			scrap_timestamp=Formatter.str_to_ts(TimestampFormat.DATETIME_MS, f"{r[0]} {r[1]}"),
	# 			name=r[2],
	# 			local_path=r[3],
	# 			impressions=r[4]
	# 		)
	#
	# 	stmt = f"""
	# 		select ts_date, ts_time, name, local_path, impressions
	# 		from {_Tables.SCRAP_ITEMS.value}
	# 		inner join {_Tables.SCRAP_STAT.value}
	# 			on {_Tables.SCRAP_STAT.value}.scrap_stat_id={_Tables.SCRAP_ITEMS.value}.scrap_stat_id
	# 		where source=:source
	# 		order by ts_date desc, ts_time desc
	# 		limit :limit"""
	#
	# 	binds = {
	# 		"source": self._scrap_source.value,
	# 		"limit": item_limit
	# 	}
	#
	# 	return self._sqlite_api.read(stmt, binds, _row_mapper)
