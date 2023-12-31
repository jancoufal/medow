import pathlib
import sqlite3


class SqliteApi(object):
	SELECT_LIMIT_MIN = 1
	SELECT_LIMIT_MAX = 300
	SELECT_LIMIT_FALLBACK = 10

	def __init__(self, sqlite_datafile: pathlib.Path):
		self.sqlite_datafile = sqlite_datafile

	@staticmethod
	def clamp_limit(limit_value: int):
		if not isinstance(limit_value, int):
			return SqliteApi.SELECT_LIMIT_FALLBACK

		if limit_value < SqliteApi.SELECT_LIMIT_MIN:
			return SqliteApi.SELECT_LIMIT_MIN

		if limit_value > SqliteApi.SELECT_LIMIT_MAX:
			return SqliteApi.SELECT_LIMIT_MAX

		return limit_value

	def do_with_connection(self, connection_cb: callable):
		db_conn = sqlite3.Connection(self.sqlite_datafile)
		try:
			with db_conn:
				return connection_cb(db_conn)
		finally:
			db_conn.close()

	def do_with_cursor(self, cursor_cb: callable):
		def _cursor_call(connection):
			db_cursor = connection.cursor()
			try:
				cb_result = cursor_cb(db_cursor)
				connection.commit()
				return cb_result
			finally:
				db_cursor.close()

		return self.do_with_connection(_cursor_call)

	def read(self, sql_stmt: str, binds, row_mapper: callable = None):
		def _reader(cursor):
			r_mapper = row_mapper if row_mapper is not None else lambda row: row
			result = list()
			for r in cursor.execute(sql_stmt, binds):
				result.append(r_mapper(r))
			return result

		return self.do_with_cursor(_reader)

	def compose_and_read(
			self,
			source_table: str,
			joins: str,
			column_list: list,
			filter_map: dict,
			order_tuple_list: tuple,
			limit: int
	):
		stmt = f"select {', '.join(column_list)} from {source_table}"

		if joins is not None:
			stmt += " " + joins

		if filter_map is not None and len(filter_map) > 0:
			stmt += " where " + " and ".join(f"{k}=:{k}" for k in filter_map.keys())

		if order_tuple_list is not None and len(order_tuple_list) > 0:
			stmt += " order by " + ", ".join(f"{_1} {_2}" for (_1, _2) in order_tuple_list)

		stmt += " limit " + str(SqliteApi.clamp_limit(limit))

		return self.read(stmt, filter_map)

	def write(self, table_name, value_mapping: dict):
		def _writer(connection):
			cols = list(value_mapping.keys())
			sql_stmt = f"insert into {table_name}({', '.join(cols)}) values (:{', :'.join(cols)})"
			connection.execute(sql_stmt, value_mapping)

		return self.do_with_connection(_writer)

	def update(self, table_name, value_mapping: dict, where_condition_mapping: dict):
		def _writer(connection):
			# rename all value_mapping keys to "new_{key}" and where_condition_mapping keys to "where_{key}"
			# statement pattern:
			# update table_name set col_a=:new_col_a, col_b=:new_col_b where col_c=:where_col_c and col_d=:where_col_d
			stmt_set = ", ".join(map(lambda k: f"{k}=:new_{k}", value_mapping.keys()))
			stmt_whr = " and ".join(map(lambda k: f"{k}=:where_{k}", where_condition_mapping.keys()))
			sql_stmt = f"update {table_name} set {stmt_set} where {stmt_whr}"
			connection.execute(sql_stmt, {
				**{f"new_{k}": v for (k, v) in value_mapping.items()},
				**{f"where_{k}": v for (k, v) in where_condition_mapping.items()}
			})

		return self.do_with_connection(_writer)

	def read_last_seq(self, table_name):
		def _reader(cursor):
			cursor.execute("select seq from sqlite_sequence where name=?", (table_name,))
			return cursor.fetchone()[0]

		return self.do_with_cursor(_reader)
