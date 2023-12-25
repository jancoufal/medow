import sys
from enum import Enum
import datetime

NOT_AVAILABLE_STR = "n/a"

class TIMESTAMP_FORMAT(Enum):
	DATE = "%Y-%m-%d"
	WEEK = "%Y-%V"
	TIME = "%H:%M.%S"
	TIME_MS = "%H:%M.%S,%f"
	DATETIME = "%Y-%m-%d %H:%M.%S"
	DATETIME_MS = "%Y-%m-%d %H:%M.%S,%f"

def ts_to_str(format:TIMESTAMP_FORMAT, ts:datetime.datetime.timestamp=None):
	_ts = ts if ts is not None else datetime.datetime.now()
	return _ts.strftime(format.value)

def str_to_ts(format:TIMESTAMP_FORMAT, ts_string:str):
	return datetime.datetime.strptime(ts_string, format.value)

def ts_diff_to_str(ts_start:datetime.datetime, ts_end:datetime.datetime, include_ms):
	return td_format((ts_start - ts_end) if ts_start > ts_end else (ts_end - ts_start), include_ms)

def td_format(td:datetime.timedelta, include_ms):
	s = [f"{td.microseconds // 1000}ms"] if include_ms else []
	r = td.total_seconds()
	for (period, factor) in [("s", 60), ("m", 60), ("h", 24), ("d", 7), ("w", None)]:
		if r > 0:
			r, v = divmod(r, factor) if factor is not None else (0, r)
			s.append(f"{v:.0f}{period}")
	return " ".join(s[::-1])


def percentage_str(count:int, total:int):
	return NOT_AVAILABLE_STR if total == 0 else f"{(100.0 * count) / total:3.2f}%"


if __name__ == "__main__":
	ts = datetime.datetime.now()
	for fmt in TIMESTAMP_FORMAT:
		if fmt == TIMESTAMP_FORMAT.WEEK:
			s = ts_to_str(fmt)
			print(f"{fmt.name}: {s}")
		else:
			s = ts_to_str(fmt)
			print(f"{fmt.name}: {s} <-> {str_to_ts(fmt, s)}")

	print(percentage_str(3, 10))
