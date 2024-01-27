from sqlite3 import Connection
from msqlite_api import SqliteApi


class RepositoryInstaller(object):
	def __init__(self, sql_api: SqliteApi):
		self._sql_api = sql_api

	def create_tables(self):
		def _create_tables_impl(c: Connection):
			c.execute("""CREATE TABLE IF NOT EXISTS task(
				pk_id INTEGER PRIMARY KEY AUTOINCREMENT,
				ref_id INTEGER,
				task_class TEXT,
				task_type TEXT,
				ts_start TEXT,
				ts_end TEXT,
				status TEXT,
				item_count_success INTEGER,
				item_count_fail INTEGER,
				exception_type TEXT,
				exception_value TEXT
			);""")

			c.execute("""CREATE TABLE IF NOT EXISTS task_item(
				pk_id INTEGER PRIMARY KEY AUTOINCREMENT,
				ref_id INTEGER,
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

		self._sql_api.do_with_connection(_create_tables_impl)
