import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

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
	def load_from_datafile(cls, datafile_path: Path):
		api = SqliteApi(datafile_path)

		return IBData(
			stat=api.read("select * from scrap_stat order by scrap_stat_id", {}, lambda r: IBScrapStat(*r)),
			items=api.read("select * from scrap_items order by scrap_item_id", {}, lambda r: IBScrapItem(*r)),
			fails=api.read("select * from scrap_fails order by scrap_fail_id", {}, lambda r: IBScrapFail(*r)),
		)


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


def store_entity(conn: sqlite3.Connection, entity: MScrapTaskE | MScrapTaskItemE, need_last_id: bool) -> int | None:
	match entity:
		case MScrapTaskE():
			table_name = "scrap_task"
		case MScrapTaskItemE():
			table_name = "scrap_task_item"
		case _:
			raise ValueError(f"Unknown entity {entity}.")

	entity_as_dict = asdict(entity)
	col_names = ",".join(entity_as_dict.keys())
	bind_names = ",".join((":" + c for c in entity_as_dict.keys()))
	stmt = f"INSERT INTO {table_name}({col_names}) values ({bind_names})"
	if need_last_id:
		cur = conn.cursor()
		cur.execute(stmt, entity_as_dict)
		last_id = cur.lastrowid
		cur.connection.commit()
		cur.close()
		return last_id
	else:
		return None


def migrate():
	print("Loading data from source DB...")
	src_data = IBData.load_from_datafile(Path("sql/image_box.sqlite3"))

	print("Opening destination DB...")
	dst_db = SqliteApi(Path("sql/medow.sqlite3"))

	def drop_tables(c: sqlite3.Cursor):
		c.execute("DROP TABLE IF EXISTS scrap_task")
		c.execute("DROP TABLE IF EXISTS scrap_task_item")

	print("Dropping tables...")
	dst_db.do_with_cursor(drop_tables)

	def reset_autoincrement_counters(c: sqlite3.Cursor):
		c.execute("DELETE FROM sqlite_sequence")
	print("Resetting autoincrement counters...")
	dst_db.do_with_cursor(reset_autoincrement_counters)

	def create_tables(c: sqlite3.Cursor):
		c.execute("""CREATE TABLE IF NOT EXISTS scrap_task(
			pk_id INTEGER PRIMARY KEY AUTOINCREMENT,
			scrapper TEXT,
			ts_start TEXT,
			ts_end TEXT,
			status TEXT,
			item_count_success INTEGER,
			item_count_fail INTEGER,
			exception_type TEXT,
			exception_value TEXT
		);""")

		c.execute("""CREATE TABLE IF NOT EXISTS scrap_task_item(
			pk_id INTEGER PRIMARY KEY AUTOINCREMENT,
			task_id INTEGER,
			ts_start TEXT,
			ts_end TEXT,
			status TEXT,
			item_name TEXT,
			local_path TEXT,
			exception_type TEXT,
			exception_value TEXT,
			FOREIGN KEY (task_id) REFERENCES scrap_task(pk_id)
		);""")

	print("Creating tables...")
	dst_db.do_with_cursor(create_tables)

	def insert_scrap_tasks(c: sqlite3.Connection):
		old_id_to_new_id = {}
		for r in src_data.stat:
			e = MScrapTaskE(
				pk_id=r.scrap_stat_id,
				scrapper=r.source,
				ts_start=f"{r.ts_start_date} {r.ts_start_time}",
				ts_end=f"{r.ts_end_date} {r.ts_end_time}" if r.ts_end_date is not None else None,
				status=r.status,
				item_count_success=r.count_success,
				item_count_fail=r.count_fail,
				exception_type=r.exc_type,
				exception_value=r.exc_value,
			)
			new_id = store_entity(c, e, True)
			old_id_to_new_id[r.scrap_stat_id] = new_id
		return old_id_to_new_id

	print("Inserting scrap tasks...")
	task_id_map = dst_db.do_with_connection(insert_scrap_tasks)

	def read_scrap_task_items(task_id_map: dict[int, int]) -> List[MScrapTaskItemE]:
		task_items = []
		for r in src_data.items:
			if r.scrap_stat_id is not None:
				task_items.append(MScrapTaskItemE(
					pk_id=None,
					task_id=task_id_map[r.scrap_stat_id],
					ts_start=f"{r.ts_date} {r.ts_time}",
					ts_end=None,
					status="finished",
					item_name=r.name,
					local_path=r.local_path,
					exception_type=None,
					exception_value=None,
				))

		for r in src_data.fails:
			if r.scrap_stat_id is not None:
				task_items.append(MScrapTaskItemE(
					pk_id=None,
					task_id=task_id_map[r.scrap_stat_id],
					ts_start=f"{r.ts_date} {r.ts_time}",
					ts_end=None,
					status="failed",
					item_name=r.item_name,
					local_path=None,
					exception_type=r.exc_type,
					exception_value=r.exc_value,
				))
		return task_items

	print("Reading scrap task items...")
	task_items = read_scrap_task_items(task_id_map)
	print(f"{len(task_items)} items read.")

	print("Sorting scrap items by date...")
	task_items.sort(key=lambda e: e.ts_start)

	def insert_scrap_task_items(c: sqlite3.Connection, task_items: List[MScrapTaskItemE]):
		for task_item in task_items:
			store_entity(c, task_item, False)

	print("Writing scrap items...")
	dst_db.do_with_connection(lambda c: insert_scrap_task_items(c, task_items))

	print("Done.")


if __name__ == "__main__":
	migrate()
