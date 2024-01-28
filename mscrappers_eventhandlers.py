from logging import Logger

from mformatters import Formatter, TimestampFormat
from mrepository import Repository
from mrepository_entities import MTaskE, TaskStatusEnum, MTaskItemE

from mscrappers_api import TaskEvents
from mrepository_entities import TaskClassAndType


class TaskEventLogger(TaskEvents):
	def __init__(self, logger: Logger, task_def: TaskClassAndType):
		self._l = logger.getChild(str(task_def))

	def on_new(self) -> None:
		self._l.info(f"Task created.")

	def on_start(self) -> None:
		self._l.info(f"Task started.")

	def on_finish(self) -> None:
		self._l.info(f"Task finished.")

	def on_error(self, ex: Exception) -> None:
		self._l.error(f"Task error: {ex!s}.")

	def on_item_start(self, item_name: str, ref_id: int | None = None) -> None:
		self._l.info(f"Item '{item_name}' started (ref_id: {ref_id}).")

	def on_item_progress(self, description: str) -> None:
		self._l.debug(f"Item progress: {description}.")

	def on_item_finish(self, destination_path: str | None) -> None:
		self._l.info(f"Item finished: '{destination_path}'.")

	def on_item_error(self, ex: Exception) -> None:
		self._l.error(f"Item error: {ex!s}.")


class TaskEventRepositoryWriter(TaskEvents):
	def __init__(self, repository: Repository, task_def: TaskClassAndType):
		self._repository = repository
		self._task_def = task_def
		self._entity_task = None
		self._entity_task_item = None

	@staticmethod
	def _get_current_timestamp() -> str:
		return Formatter.ts_to_str(TimestampFormat.DATETIME_MS)

	def on_new(self) -> None:
		self._entity_task = MTaskE(
			pk_id=None,
			task_class=self._task_def.cls.value,
			task_type=self._task_def.typ.value,
			ts_start=TaskEventRepositoryWriter._get_current_timestamp(),
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
		self._entity_task.ts_start = TaskEventRepositoryWriter._get_current_timestamp()
		self._repository.update_entity(self._entity_task)

	def on_finish(self) -> None:
		self._entity_task.status = TaskStatusEnum.COMPLETED.value
		self._entity_task.ts_end = TaskEventRepositoryWriter._get_current_timestamp()
		self._repository.update_entity(self._entity_task)

	def on_error(self, ex: Exception) -> None:
		self._entity_task.status = TaskStatusEnum.ERROR.value
		self._entity_task.ts_end = TaskEventRepositoryWriter._get_current_timestamp()
		self._entity_task.exception_type = ex.__class__.__name__
		self._entity_task.exception_value = str(ex)
		self._repository.update_entity(self._entity_task)

	def on_item_start(self, item_name: str, ref_id: int | None = None) -> None:
		self._entity_task_item = MTaskItemE(
			pk_id=None,
			ref_id=ref_id,
			task_id=self._entity_task.pk_id,
			ts_start=TaskEventRepositoryWriter._get_current_timestamp(),
			ts_end=None,
			status=TaskStatusEnum.RUNNING.value,
			item_name=item_name,
			destination_path=None,
			exception_type=None,
			exception_value=None
		)
		pk_id = self._repository.save_entity(self._entity_task_item, True)
		self._entity_task_item.pk_id = pk_id

	def on_item_progress(self, description: str) -> None:
		# do nothing
		pass

	def on_item_finish(self, destination_path: str | None) -> None:
		self._entity_task_item.status = TaskStatusEnum.COMPLETED.value
		self._entity_task_item.ts_end = TaskEventRepositoryWriter._get_current_timestamp()
		self._entity_task_item.destination_path = destination_path
		self._repository.update_entity(self._entity_task_item)
		self._entity_task.item_count_success += 1

	def on_item_error(self, ex: Exception) -> None:
		self._entity_task_item.status = TaskStatusEnum.ERROR.value
		self._entity_task_item.ts_end = TaskEventRepositoryWriter._get_current_timestamp()
		self._entity_task_item.exception_type = ex.__class__.__name__
		self._entity_task_item.exception_value = str(ex)
		self._repository.update_entity(self._entity_task_item)
		self._entity_task.item_count_fail += 1
