from abc import ABC, abstractmethod
from typing import Tuple


class ScrapperEvents(ABC):
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
	def on_item_start(self, item_name: str) -> None:
		pass

	@abstractmethod
	def on_item_progress(self, description: str) -> None:
		pass

	@abstractmethod
	def on_item_finish(self, local_path: str | None) -> None:
		pass

	@abstractmethod
	def on_item_error(self, ex: Exception) -> None:
		pass


class ScrapperEventDispatcher(ScrapperEvents):
	def __init__(self, event_handlers: Tuple[ScrapperEvents, ...]):
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

	def on_item_start(self, item_name: str) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_item_start(item_name)

	def on_item_progress(self, description: str) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_item_progress(description)

	def on_item_finish(self, local_path: str | None) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_item_finish(local_path)

	def on_item_error(self, ex: Exception) -> None:
		for event_handler in self._event_handlers:
			event_handler.on_item_error(ex)
