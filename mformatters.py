from enum import Enum
from datetime import datetime, timedelta


class TimestampFormat(Enum):
	DATE = "%Y-%m-%d"
	WEEK = "%Y-%V"
	TIME = "%H:%M.%S"
	TIME_MS = "%H:%M.%S,%f"
	DATETIME = "%Y-%m-%d %H:%M.%S"
	DATETIME_MS = "%Y-%m-%d %H:%M.%S,%f"


class Formatter(object):
	NOT_AVAILABLE_STR = "n/a"

	@staticmethod
	def ts_to_str(fmt: TimestampFormat, ts: datetime = None):
		_ts = ts if ts is not None else datetime.now()
		return _ts.strftime(fmt.value)

	@staticmethod
	def str_to_ts(fmt: TimestampFormat, ts_string: str):
		return datetime.strptime(ts_string, fmt.value)

	@staticmethod
	def str_to_ts_safe(fmt: TimestampFormat, ts_string: str, default_value: str | None):
		try:
			return datetime.strptime(ts_string, fmt.value)
		except:
			return default_value

	@staticmethod
	def ts_diff_to_str(ts_start: datetime, ts_end: datetime, include_ms: bool):
		return Formatter.td_format((ts_start - ts_end) if ts_start > ts_end else (ts_end - ts_start), include_ms)

	@staticmethod
	def td_format(td: timedelta, include_ms: bool):
		s = [f"{td.microseconds // 1000}ms"] if include_ms else []
		r = td.total_seconds()
		for (period, factor) in [("s", 60), ("m", 60), ("h", 24), ("d", 7), ("w", None)]:
			if r > 0:
				r, v = divmod(r, factor) if factor is not None else (0, r)
				s.append(f"{v:.0f}{period}")
		return " ".join(s[::-1])

	@staticmethod
	def percentage_str(count: int, total: int):
		return Formatter.NOT_AVAILABLE_STR if total == 0 else f"{(100.0 * count) / total:3.2f}%"

	@staticmethod
	def percentage_str_safe(count: int, total: int, default_value: str):
		try:
			return Formatter.NOT_AVAILABLE_STR if total == 0 else f"{(100.0 * count) / total:3.2f}%"
		except:
			return default_value
