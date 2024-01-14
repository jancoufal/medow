from time import sleep
from logging import Logger

from mconfig import Config
from mrepository import Repository
from mscrappers_api import ScrapperType, ScrapperEvents, ScrapperEventDispatcher
from mscrappers_eventhandlers import ScrapperEventLogger, ScrapperEventRepositoryWriter
from mformatters import Formatter


class TaskFactory(object):
	def __init__(self, logger: Logger, config: Config, repository_persistent: Repository, repository_in_memory: Repository):
		self._logger = logger
		self._config = config
		self._repository_persistent = repository_persistent
		self._repository_in_memory = repository_in_memory

	def create_task_dummy(self, description: str):
		eh = ScrapperEventDispatcher((
			ScrapperEventLogger(self._logger, ScrapperType.DUMMY),
			ScrapperEventRepositoryWriter(self._repository_in_memory, ScrapperType.DUMMY),
		))
		return _TaskDummy(eh, description)


class _TaskDummy(object):
	def __init__(self, scrapper_event_handler: ScrapperEvents, description: str):
		self._event = scrapper_event_handler
		self._description = description

	def __call__(self):
		i_max, j_max = 10, 10
		self._event.on_start()
		for i in range(i_max):
			self._event.on_item_start(f"item #{i+1} of #{i_max}")
			for j in range(j_max):
				sleep(.1)
				self._event.on_item_progress(f"item #{i+1} progress: {Formatter.percentage_str(j+1, j_max)}")
			self._event.on_item_finish(None)
		self._event.on_finish()