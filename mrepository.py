"""
persistent repository implementation
"""

from logging import Logger
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import List
import sqlite3

from mrepositoryentities import *
from mscrappers_api import ScrapperType
from msqlite_api import SqliteApi


class _Tables(Enum):
	SCRAP_TASK = "scrap_task"
	SCRAP_TASK_ITEM = "scrap_task_item"


class _ScrapState(Enum):
	IN_PROGRESS = "in_progress"
	COMPLETE = "complete"
	FAILED = "failed"


class RepositoryInterface(ABC):
	@abstractmethod
	def save_entity(self, entity: MScrapTaskE | MScrapTaskItemE, get_last_id: bool):
		pass

	@abstractmethod
	def update_entity(self, entity: MScrapTaskE | MScrapTaskItemE) -> None:
		pass


class Repository(RepositoryInterface):
	def __init__(self, logger: Logger, sqlite_api: SqliteApi):
		super().__init__()
		self._logger = logger
		self._sqlite_api = sqlite_api

	@staticmethod
	def _get_entity_table(entity: MScrapTaskE | MScrapTaskItemE) -> str:
		match entity:
			case MScrapTaskE(): return "scrap_task"
			case MScrapTaskItemE(): return "scrap_task_item"
			case _: raise ValueError(f"Unknown entity {entity}.")

	def get_sqlite_api(self) -> SqliteApi:
		return self._sqlite_api

	def save_entity(self, entity: MScrapTaskE | MScrapTaskItemE, get_last_id: bool) -> int | None:
		table_name = Repository._get_entity_table(entity)
		entity_as_dict = asdict(entity)
		col_names = ",".join(entity_as_dict.keys())
		bind_names = ",".join((":" + c for c in entity_as_dict.keys()))
		stmt = f"INSERT INTO {table_name}({col_names}) values ({bind_names})"

		def _exec_without_id_return(con: sqlite3.Connection):
			self._logger.debug(f"SQL: {stmt}, entity: {entity_as_dict}")
			con.execute(stmt, entity_as_dict)
			con.commit()
			return None

		def _exec_with_id_return(cur: sqlite3.Cursor):
			self._logger.debug(f"SQL: {stmt}, entity: {entity_as_dict}")
			cur.execute(stmt, entity_as_dict)
			last_id = cur.lastrowid
			self._logger.debug(f"SQL: ...last_id: {last_id}")
			cur.connection.commit()
			return last_id

		self._logger.debug(f"Saving entity {entity.__class__.__name__}.")

		if get_last_id:
			return self._sqlite_api.do_with_cursor(_exec_with_id_return)
		else:
			return self._sqlite_api.do_with_connection(_exec_without_id_return)

	def update_entity(self, entity: MScrapTaskE | MScrapTaskItemE) -> None:
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
			self._logger.debug(f"SQL: {stmt}, WHR: {stmt_whr}")
			conn.execute(stmt, stmt_whr)

		self._logger.debug(f"Updating entity {entity.__class__.__name__}.")
		self._sqlite_api.do_with_connection(_updater)

	def load_entity_scrap_task(self, pk_id: int) -> MScrapTaskE | None:
		self._logger.debug(f"Reading entity 'MScrapTaskE' for pk_id '{pk_id}'.")
		return self._sqlite_api.read(
			f"select * from {_Tables.SCRAP_TASK.value} where pk_id=:pk_id",
			{"pk_id": pk_id},
			lambda rs: MScrapTaskE(*rs)
		).pop()

	def read_recent_scrap_tasks_all(self, item_limit: int) -> List[MScrapTaskE]:
		self._logger.debug(f"Reading entities 'MScrapTaskE' for all scrappers limited to {item_limit} items.")
		return self._sqlite_api.read(
			sql_stmt=f"select * from {_Tables.SCRAP_TASK.value} order by pk_id desc limit :limit",
			binds={"limit": item_limit},
			row_mapper=lambda rs: MScrapTaskE(*rs)
		)

	def read_recent_scrap_tasks(self, scrapper_type: ScrapperType, item_limit: int) -> List[MScrapTaskE]:
		self._logger.debug(f"Reading entities 'MScrapTaskE' for scrapper '{scrapper_type.value}' limited to {item_limit} items.")
		return self._sqlite_api.read(
			sql_stmt=f"select * from {_Tables.SCRAP_TASK.value} where scrapper=:scrapper order by pk_id desc limit :limit",
			binds={"scrapper": scrapper_type.value, "limit": item_limit},
			row_mapper=lambda rs: MScrapTaskE(*rs)
		)

	def read_scrap_task_items(self, task_entity: MScrapTaskE) -> List[MScrapTaskItemE]:
		self._logger.debug(f"Reading entities 'MScrapTaskItemE' for task entity '{task_entity.pk_id}.")
		return self._sqlite_api.read(
			sql_stmt=f"select * from {_Tables.SCRAP_TASK_ITEM.value} where task_id=:task_id order by pk_id asc",
			binds={"task_id": task_entity.pk_id},
			row_mapper=lambda rs: MScrapTaskItemE(*rs)
		)

	def read_recent_scrap_task_items(self, scrapper_type: ScrapperType, item_limit: int) -> List[MScrapTaskItemE]:
		self._logger.debug(f"Reading recent entities 'MScrapTaskE' for scrapper '{scrapper_type.value}' limited to {item_limit} items.")
		return self._sqlite_api.read(
			sql_stmt=f"select sti.* from {_Tables.SCRAP_TASK.value} st inner join {_Tables.SCRAP_TASK_ITEM.value} sti on sti.task_id=st.pk_id where st.scrapper=:scrapper order by sti.pk_id desc limit :limit",
			binds={"scrapper": scrapper_type.value, "limit": item_limit},
			row_mapper=lambda rs: MScrapTaskItemE(*rs)
		)
