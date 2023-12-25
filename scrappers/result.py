import sys, traceback
from enum import Enum, auto
import typing
import pathlib
import datetime
from .sources import Source
from .util.exception_info import ExceptionInfo
from .util.formatters import percentage_str


class ResultItemStatus(Enum):
	SUCCEEDED = auto()
	FAILED = auto()


class ResultItemSuccessInfo(object):
	def __init__(self, relative_file_path: str, remote_file_url: str):
		self._relative_file_path = relative_file_path
		self._remote_file_url = remote_file_url

	def __str__(self):
		return f"{self.relative_file_path=}, {self.remote_file_url=}"

	@property
	def relative_file_path(self):
		return self._relative_file_path

	@property
	def remote_file_url(self):
		return self._remote_file_url


class ResultItemFailedInfo(object):
	def __init__(self, item_to_download: str, exception_info: ExceptionInfo):
		self._item_to_download = item_to_download
		self._exception_info = exception_info

	def __str__(self):
		return f"{self.item_to_download=}, {self._exception_info=!s}"
		
	@property
	def item_to_download(self):
		return self._item_to_download

	@property
	def e_info(self):
		return self._exception_info


class ResultItem(object):
	@classmethod
	def createSucceeded(cls, relative_file_path: str, remote_file_url: str):
		item_info = ResultItemSuccessInfo(relative_file_path, remote_file_url)
		return cls(ResultItemStatus.SUCCEEDED, item_info, None)

	@classmethod
	def createFailed(cls, item_to_download: str, exception_info:ExceptionInfo=None):
		e_info = exception_info if exception_info is not None else ExceptionInfo.createFromLastException()
		item_info = ResultItemFailedInfo(item_to_download, e_info)
		return cls(ResultItemStatus.FAILED, None, item_info)

	def __init__(self, status: ResultItemStatus, item_info_success: ResultItemSuccessInfo, item_info_error: ResultItemFailedInfo):
		self._status = status
		self._s_info = item_info_success
		self._e_info = item_info_error

	def __str__(self):
		return f"{self.status.name}, {self.error_info=!s}, {self.success_info=!s}"

	@property
	def status(self):
		return self._status

	@property
	def error_info(self):
		return self._e_info

	@property
	def success_info(self):
		return self._s_info


class Result(object):
	def __init__(self, source: Source, ts_start: datetime.datetime=None):
		self._source = source
		self._ts_start = ts_start if ts_start is not None else datetime.datetime.now()
		self._time_taken = "unknown"
		self._items = list()
		self._general_error = list()

	def __str__(self):
		return f"Result of [{self._source.value}] scrapper: {self.items_succeeded_count} of {self.items_count} ({self.success_percentage_str}) scrapped in {self.time_taken}"

	def on_item(self, result_item: ResultItem):
		self._items.append(result_item)

	def on_scrapping_finished(self):
		self._time_taken = str(datetime.datetime.now() - self._ts_start)

	def on_scrapping_exception(self, error: ExceptionInfo):
		self._general_error.append(error)

	def get_items(self, item_predicate=None):
		return self._items if item_predicate is None else [item for item in self._items if item_predicate(item)]

	@property
	def time_taken(self):
		return self._time_taken

	@property
	def items(self):
		return self.get_items()

	@property
	def items_count(self):
		return len(self.items)

	@property
	def items_succeeded(self):
		return self.get_items(lambda item: item.status == ResultItemStatus.SUCCEEDED)

	@property
	def items_succeeded_count(self):
		return len(self.items_succeeded)

	@property
	def items_failed(self):
		return self.get_items(lambda item: item.status == ResultItemStatus.FAILED)

	@property
	def items_failed_count(self):
		return len(self.items_failed)

	@property
	def success_percentage_str(self):
		return percentage_str(self.items_succeeded_count, self.items_count)

	@property
	def general_error_list(self):
		return self._general_error
