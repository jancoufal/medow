from logging import Logger

from mformatters import Formatter, TimestampFormat
from mrepository import Repository
from mrepositoryentities import MScrapTaskE, TaskStatusEnum, MScrapTaskItemE

from mscrappers_api import ScrapperEvents, ScrapperType


class ScrapperEventLogger(ScrapperEvents):
	def __init__(self, logger: Logger, scrapper_type: ScrapperType):
		self._l = logger.getChild(scrapper_type.value)

	def on_new(self) -> None:
		self._l.info(f"Task created.")

	def on_start(self) -> None:
		self._l.info(f"Task started.")

	def on_finish(self) -> None:
		self._l.info(f"Task finished.")

	def on_error(self, ex: Exception) -> None:
		self._l.error(f"Task error: {ex!s}.")

	def on_item_start(self, item_name: str) -> None:
		self._l.info(f"Item '{item_name}' started.")

	def on_item_progress(self, description: str) -> None:
		self._l.debug(f"Item progress: {description}.")

	def on_item_finish(self, local_path: str | None) -> None:
		self._l.info(f"Item finished: '{local_path}'.")

	def on_item_error(self, ex: Exception) -> None:
		self._l.error(f"Item error: {ex!s}.")


class ScrapperEventRepositoryWriter(ScrapperEvents):
	def __init__(self, repository: Repository, scrapper_type: ScrapperType):
		self._repository = repository
		self._scrapper_type = scrapper_type
		self._entity_task = None
		self._entity_task_item = None

	@staticmethod
	def _get_current_timestamp() -> str:
		return Formatter.ts_to_str(TimestampFormat.DATETIME_MS)

	def on_new(self) -> None:
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
		pk_id = self._repository.save_entity(self._entity_task, True)
		self._entity_task.pk_id = pk_id

	def on_start(self) -> None:
		self._entity_task.status = TaskStatusEnum.RUNNING.value
		self._entity_task.ts_start = ScrapperEventRepositoryWriter._get_current_timestamp()
		self._repository.update_entity(self._entity_task)

	def on_finish(self) -> None:
		self._entity_task.status = TaskStatusEnum.COMPLETED.value
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
		self._entity_task.item_count_success += 1

	def on_item_error(self, ex: Exception) -> None:
		self._entity_task_item.status = TaskStatusEnum.ERROR.value
		self._entity_task_item.ts_end = ScrapperEventRepositoryWriter._get_current_timestamp()
		self._entity_task.exception_type = ex.__class__.__name__
		self._entity_task.exception_value = str(ex)
		self._repository.update_entity(self._entity_task_item)
		self._entity_task.item_count_fail += 1
