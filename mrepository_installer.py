from sqlite3 import Connection
from mrepository import Repository


class RepositoryInstaller(object):
	def __init__(self, repository: Repository):
		self._repository = repository

	def create_tables(self):
		def _create_tables_impl(c: Connection):
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

		self._repository.get_sqlite_api().do_with_connection(_create_tables_impl)
