from enum import Enum
from abc import ABCMeta, abstractmethod


class ScrapperType(Enum):
	NOOP = "noop"
	YOUTUBE_DL = "youtube_dl"
	ROUMEN = "roumen"
	ROUMEN_MASO = "roumen-maso"

	@staticmethod
	def of(scrapper_type: str) -> "ScrapperType":
		for e in ScrapperType:
			if e.value == scrapper_type:
				return e
		return ScrapperType.NOOP


class ScrapperEvents(ABCMeta):
	@abstractmethod
	def on_start(cls) -> int:
		pass

	@abstractmethod
	def on_finish(cls, scrap_id: int) -> None:
		pass

	@abstractmethod
	def on_error(cls, scrap_id: int, exception_type: str, exception_message: str) -> None:
		pass

	@abstractmethod
	def on_item_start(cls) -> int:
		pass

	@abstractmethod
	def on_item_finish(cls, item_id: int, item_name: str, local_path: str | None) -> None:
		pass

	@abstractmethod
	def on_item_error(cls, item_id: int, item_name: str, exception_type: str, exception_message: str):
		pass
