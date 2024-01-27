import logging
from logging import Logger, basicConfig
import sqlite3
from typing import List

from mrepository import Repository, _Table
from mrepository_entities import *
from mrepository_installer import RepositoryInstaller
from msqlite_api import SqliteApi


@dataclass
class IBScrapStat:
	scrap_stat_id: int
	source: str
	ts_start_date: str
	ts_start_time: str
	ts_end_date: str
	ts_end_time: str
	status: str
	count_success: int
	count_fail: int
	exc_type: str
	exc_value: str
	exc_traceback: str


@dataclass
class IBScrapItem:
	scrap_item_id: int
	scrap_stat_id: int
	ts_date: str
	ts_week: str
	ts_time: str
	local_path: str
	name: str
	impressions: int


@dataclass
class IBScrapFail:
	scrap_fail_id: int
	scrap_stat_id: int
	ts_date: str
	ts_time: str
	item_name: str
	description: str
	exc_type: str
	exc_value: str
	exc_traceback: str


@dataclass
class IBData:
	stat: List[IBScrapStat]
	items: List[IBScrapItem]
	fails: List[IBScrapFail]

	@classmethod
	def load_from_datafile(cls, logger: Logger, datafile_path: str):
		api = SqliteApi(logger, datafile_path, False, {})

		return IBData(
			stat=api.read("select * from scrap_stat order by scrap_stat_id", {}, lambda r: IBScrapStat(*r)),
			items=api.read("select * from scrap_items order by scrap_item_id", {}, lambda r: IBScrapItem(*r)),
			fails=api.read("select * from scrap_fails order by scrap_fail_id", {}, lambda r: IBScrapFail(*r)),
		)


def migrate():
	basicConfig(level=logging.CRITICAL)
	logger = logging.getLogger()

	print("Loading data from source DB...")
	src_data = IBData.load_from_datafile(logger, "sql/image_box.sqlite3")

	print("Opening destination DB...")
	dst_db = SqliteApi(logger,"sql/medow.sqlite3", False, {})

	print("Initializing repository...")
	repository = Repository(logger, dst_db)

	def drop_tables(c: sqlite3.Cursor):
		c.execute("DROP TABLE IF EXISTS " + _Table.TASK.value)
		c.execute("DROP TABLE IF EXISTS " + _Table.TASK_ITEM.value)

	print("Dropping tables...")
	dst_db.do_with_cursor(drop_tables)

	def reset_autoincrement_counters(c: sqlite3.Cursor):
		c.execute("DELETE FROM sqlite_sequence")
	print("Resetting autoincrement counters...")
	dst_db.do_with_cursor(reset_autoincrement_counters)

	print("Creating tables...")
	RepositoryInstaller(dst_db).create_tables()

	print("Migrating scrap tasks...")
	tasks = []
	source_to_task_class_map = {
		"roumen": TaskClass.SCRAP.value,
		"roumen-maso": TaskClass.SCRAP.value,
	}

	source_to_task_type_map = {
		"roumen": TaskType.ROUMEN_KECY.value,
		"roumen-maso": TaskType.ROUMEN_MASO.value,
	}

	error_map = {
		"<class 'requests.exceptions.SSLError'>": "SSLError",
		"<class 'requests.exceptions.ConnectionError'>": "ConnectionError",
		"<class 'urllib.error.HTTPError'>": "HTTPError",
		"<class 'NameError'>": "NameError",
		"<class 'TypeError'>": "TypeError",
	}

	for r in src_data.stat:
		tasks.append(MScrapTaskE(
			pk_id=r.scrap_stat_id,
			ref_id=None,
			task_class=source_to_task_class_map[r.source],
			task_type=source_to_task_type_map[r.source],
			ts_start=f"{r.ts_start_date} {r.ts_start_time}",
			ts_end=f"{r.ts_end_date} {r.ts_end_time}" if r.ts_end_date is not None else None,
			status=r.status,
			item_count_success=r.count_success if r.count_success is not None else 0,
			item_count_fail=r.count_fail if r.count_fail is not None else 0,
			exception_type=error_map[r.exc_type] if r.exc_type is not None else None,
			exception_value=r.exc_value,
		))
	print(f"{len(tasks)} tasks read.")

	print("Writing tasks...")
	task_id_map = {}
	for task in tasks:
		old_id = task.pk_id
		task.pk_id = None
		new_id = repository.save_entity(task, True)
		task_id_map[old_id] = new_id

	def migrating_scrap_task_items(task_id_map: dict[int, int]) -> List[MScrapTaskItemE]:
		task_items = []
		for r in src_data.items:
			if r.scrap_stat_id is not None:
				task_items.append(MScrapTaskItemE(
					pk_id=None,
					ref_id=None,
					task_id=task_id_map[r.scrap_stat_id],
					ts_start=f"{r.ts_date} {r.ts_time}",
					ts_end=None,
					status=TaskStatusEnum.COMPLETED.value,
					item_name=r.name,
					local_path=r.local_path,
					exception_type=None,
					exception_value=None,
				))

		for r in src_data.fails:
			if r.scrap_stat_id is not None:
				task_items.append(MScrapTaskItemE(
					pk_id=None,
					ref_id=None,
					task_id=task_id_map[r.scrap_stat_id],
					ts_start=f"{r.ts_date} {r.ts_time}",
					ts_end=None,
					status=TaskStatusEnum.ERROR.value,
					item_name=r.item_name,
					local_path=None,
					exception_type=error_map[r.exc_type],
					exception_value=r.exc_value,
				))
		return task_items

	print("Migrating scrap task items...")
	task_items = migrating_scrap_task_items(task_id_map)
	print(f"{len(task_items)} items read.")

	print("Sorting scrap items by date...")
	task_items.sort(key=lambda e: e.ts_start)

	print("Writing scrap items...")
	for task_item in task_items:
		repository.save_entity(task_item, False)

	print("Done.")


if __name__ == "__main__":
	migrate()
