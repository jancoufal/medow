from enum import Enum
from abc import ABC, abstractmethod
from logging import Logger
from typing import List
from mformatters import Formatter, TimestampFormat
from mrepository import Repository
from mrepositoryentities import TaskStatusEnum, MScrapTaskE, MScrapTaskItemE


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


class ScrapperEvents(ABC):
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
	def __init__(self, event_handlers: List[ScrapperEvents]):
		self._event_handlers = event_handlers

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


class ScrapperEventLogger(ScrapperEvents):
	def __init__(self, logger: Logger, scrapper_type: ScrapperType):
		self._l = logger.getChild(scrapper_type.value)

	def on_start(self) -> None:
		self._l.info(f"Started.")

	def on_finish(self) -> None:
		self._l.info(f"Finished.")

	def on_error(self, ex: Exception) -> None:
		self._l.error(f"Error: {ex!s}.")

	def on_item_start(self, item_name: str) -> None:
		self._l.info(f"Item {item_name} started.")

	def on_item_progress(self, description: str) -> None:
		self._l.debug(f"Item progress: {description}.")

	def on_item_finish(self, local_path: str | None) -> None:
		self._l.info(f"Item finished: {local_path}.")

	def on_item_error(self, ex: Exception) -> None:
		self._l.error(f"Item error: {ex!s}.")


class ScrapperEventRepositoryWriter(ScrapperEvents):
	def __init__(self, repository: Repository, scrapper_type: ScrapperType):
		super().__init__(ScrapperType)
		self._repository = repository
		self._scrapper_type = scrapper_type
		self._entity_task = MScrapTaskE(
			pk_id=None,
			scrapper=self._scrapper_type.value,
			ts_start=ScrapperEventRepositoryWriter._get_current_timestamp(),
			ts_end=None,
			status=TaskStatusEnum.CREATED.value,
			item_count_fail=0,
			item_count_success=0,
			exception_type=None,
			exception_value=None
		)
		self._entity_task_item = None

	@staticmethod
	def _get_current_timestamp() -> str:
		return Formatter.ts_to_str(TimestampFormat.DATETIME_MS)

	def on_start(self) -> None:
		self._entity_task.status = TaskStatusEnum.RUNNING.value
		self._entity_task.ts_start = ScrapperEventRepositoryWriter._get_current_timestamp()
		pk_id = self._repository.save_entity(self._entity_task, True)
		self._entity_task.pk_id = pk_id

	def on_finish(self) -> None:
		self._entity_task.status = TaskStatusEnum.RUNNING.value
		self._entity_task.ts_end = ScrapperEventRepositoryWriter._get_current_timestamp()
		self._repository.update_entity(self._entity_task)

	def on_error(self, ex: Exception) -> None:
		self._entity_task.status = TaskStatusEnum.ERROR.value
		self._entity_task.ts_end = ScrapperEventRepositoryWriter._get_current_timestamp()
		self._entity_task.exception_type = ex.__class__.__name__
		self._entity_task.exception_value = str(ex)
		self._repository.update_entity(self._entity_task)

	def on_item_start(self, item_name: str) -> None:
		self._entity_task_item = MScrapTaskItemE(
			pk_id=None,
			task_id=self._entity_task.pk_id,
			ts_start=ScrapperEventRepositoryWriter._get_current_timestamp(),
			ts_end=None,
			status=TaskStatusEnum.RUNNING.value,
			item_name=item_name,
			local_path=None,
			exception_type=None,
			exception_value=None
		)

	def on_item_progress(self, description: str) -> None:
		# do nothing
		pass

	def on_item_finish(self, local_path: str | None) -> None:
		self._entity_task_item.status = TaskStatusEnum.COMPLETED.value
		self._entity_task_item.ts_end = ScrapperEventRepositoryWriter._get_current_timestamp()
		self._entity_task_item.local_path = local_path
		self._repository.update_entity(self._entity_task_item)

	def on_item_error(self, ex: Exception) -> None:
		self._entity_task_item.status = TaskStatusEnum.ERROR.value
		self._entity_task_item.ts_end = ScrapperEventRepositoryWriter._get_current_timestamp()
		self._entity_task.exception_type = ex.__class__.__name__
		self._entity_task.exception_value = str(ex)
		self._repository.update_entity(self._entity_task_item)
