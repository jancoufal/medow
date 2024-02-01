"""
persistent repository implementation
"""

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import asdict
from logging import Logger
from typing import List

from mrepository_entities import *
from msqlite_api import SqliteApi


class _Table(Enum):
	TASK = "task"
	TASK_ITEM = "task_item"

	@staticmethod
	def for_entity(entity: MTaskE | MTaskItemE) -> str:
		match entity:
			case MTaskE(): return _Table.TASK.value
			case MTaskItemE(): return _Table.TASK_ITEM.value
			case _: raise ValueError(f"Unknown entity {entity}.")


class RepositoryInterface(ABC):
	@abstractmethod
	def save_entity(self, entity: MTaskE | MTaskItemE, get_last_id: bool):
		pass

	@abstractmethod
	def update_entity(self, entity: MTaskE | MTaskItemE) -> None:
		pass


class Repository(RepositoryInterface):
	def __init__(self, logger: Logger, sqlite_api: SqliteApi):
		super().__init__()
		self._logger = logger
		self._sqlite_api = sqlite_api

	def get_sqlite_api(self) -> SqliteApi:
		return self._sqlite_api

	def save_entity(self, entity: MTaskE | MTaskItemE, get_last_id: bool) -> int | None:
		table_name = _Table.for_entity(entity)
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

	def update_entity(self, entity: MTaskE | MTaskItemE) -> None:
		def _updater(conn: sqlite3.Connection):
			# rename all value_mapping keys to "new_{key}" and where_condition_mapping keys to "whr_{key}"
			# statement pattern:
			# update table_name set col_a=:new_col_a, col_b=:new_col_b where col_c=:where_col_c and col_d=:where_col_d
			table_name = _Table.for_entity(entity)
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

	def load_entity_scrap_task(self, pk_id: int) -> MTaskE | None:
		self._logger.debug(f"Reading entity 'MScrapTaskE' for pk_id '{pk_id}'.")
		return self._sqlite_api.read(
			f"select * from {_Table.TASK.value} where pk_id=:pk_id",
			{"pk_id": pk_id},
			lambda rs: MTaskE(*rs)
		).pop()

	def read_recent_tasks_all(self, item_limit: int) -> List[MTaskE]:
		self._logger.debug(f"Reading recent entities 'MScrapTaskE' limited to {item_limit} items.")
		return self._sqlite_api.read(
			sql_stmt=f"select * from {_Table.TASK.value} order by pk_id desc limit :limit",
			binds={"limit": item_limit},
			row_mapper=lambda rs: MTaskE(*rs)
		)

	def read_scrap_task_items(self, task_entity: MTaskE) -> List[MTaskItemE]:
		self._logger.debug(f"Reading entities 'MScrapTaskItemE' for task entity '{task_entity.pk_id}.")
		return self._sqlite_api.read(
			sql_stmt=f"select * from {_Table.TASK_ITEM.value} where task_id=:task_id order by pk_id asc",
			binds={"task_id": task_entity.pk_id},
			row_mapper=lambda rs: MTaskItemE(*rs)
		)

	def read_recent_scrap_task_items(self, task_def: TaskClassAndType, item_limit: int) -> List[MTaskItemE]:
		self._logger.debug(f"Reading recent entities 'MScrapTaskE' for task '{task_def}' limited to {item_limit} items.")
		return self._sqlite_api.read(
			sql_stmt=f"""
				select ti.*
				from {_Table.TASK.value} t
				inner join {_Table.TASK_ITEM.value} ti
					on ti.task_id=t.pk_id
				where t.task_class=:task_class and t.task_type=:task_type
				order by ti.pk_id desc
				limit :limit""",
			binds={"task_class": task_def.cls.value, "task_type": task_def.typ.value, "limit": item_limit},
			row_mapper=lambda rs: MTaskItemE(*rs)
		)

	def read_task_items_not_synced(self, task_def: TaskClassAndType) -> List[MTaskItemE]:
		self._logger.debug(f"Reading non synchronized entities 'MScrapTaskE' for task '{task_def}'.")
		return self._sqlite_api.read(
			sql_stmt=f"""
				select ti.*
				from {_Table.TASK.value} t
				inner join {_Table.TASK_ITEM.value} ti
					on ti.task_id=t.pk_id and ti.sync_status=:sync_status
				where t.task_class=:task_class
					and t.task_type=:task_type
				order by ti.pk_id desc""",
			binds={
				"task_class": TaskClass.SCRAP.value,
				"task_type": task_def.typ.value,
				"sync_status": TaskSyncStatusEnum.NOT_SYNCED.value,
			},
			row_mapper=lambda rs: MTaskItemE(*rs)
		)

