import sqlite3

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
