from abc import ABC, abstractmethod
from typing import Tuple


class TaskEvents(ABC):
	@abstractmethod
	def on_new(self) -> None:
		pass

	@abstractmethod
	def on_start(self) -> None:
		pass

	@abstractmethod
	def on_finish(self) -> None:
		pass

	@abstractmethod
	def on_error(self, ex: Exception) -> None:
		pass

	@abstractmethod
	def on_item_start(self, item_name: str, ref_id: int | None = None) -> None:
		pass

	@abstractmethod
	def on_item_progress(self, description: str) -> None:
		pass

	@abstractmethod
	def on_item_finish(self, destination_path: str | None) -> None:
		pass

	@abstractmethod
	def on_item_error(self, ex: Exception) -> None:
		pass


class TaskEventDispatcher(TaskEvents):
	def __init__(self, event_handlers: Tuple[TaskEvents, ...]):
		self._event_handlers = tuple(event_handlers)

	def __str__(self):
		return f"ScrapperEventDispatcher for {len(self._event_handlers)} event handlers"

	def on_new(self) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_new()

	def on_start(self) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_start()

	def on_finish(self) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_finish()

	def on_error(self, ex: Exception) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_error(ex)

	def on_item_start(self, item_name: str, ref_id: int | None = None) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_item_start(item_name, ref_id)

	def on_item_progress(self, description: str) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_item_progress(description)

	def on_item_finish(self, destination_path: str | None) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_item_finish(destination_path)

	def on_item_error(self, ex: Exception) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_item_error(ex)
