from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from logging import Logger, basicConfig, getLogger

from flask import Flask

from mconfig import Config
from mformatters import Formatter
from mrepository import RepositoryFactory, RepositoryType, Repository
from mscrappertaskfactory import TaskFactory
from msqlite_api import SqliteApi


@dataclass
class AppContext(object):
	app: Flask
	start_time: datetime
	logger: Logger
	config: Config
	repository_persistent: Repository
	repository_in_memory: Repository
	task_factory: TaskFactory
	task_executor: ThreadPoolExecutor

	@classmethod
	def create(cls, flask_app: Flask, config_file: str):

		config = Config.from_yaml_file(config_file)

		basicConfig(
			format=config.logger.format,
			level=config.logger.level,
		)

		logger = getLogger(config.logger.name)
		logger.info(f"Logger created with level '{config.logger.level}'.")
		logger.info(f"Config '{config_file}' loaded.")

		repository_factory = RepositoryFactory(
			logger.getChild("repository"),
			SqliteApi(logger.getChild("sqlite3"), config.persistence.sqlite_datafile)
		)

		repository_persistent = repository_factory.create(RepositoryType.PERSISTENT)
		repository_in_memory = repository_factory.create(RepositoryType.IN_MEMORY)

		task_executor = ThreadPoolExecutor(max_workers=config.worker_thread.max_workers)
		logger.debug(f"Task executor {task_executor!s} created.")

		return cls(
			app=flask_app,
			start_time=datetime.now(),
			logger=logger,
			config=config,
			repository_persistent=repository_persistent,
			repository_in_memory=repository_in_memory,
			task_factory=TaskFactory(logger.getChild("task"), config, repository_persistent, repository_in_memory),
			task_executor=task_executor,
		)

	@property
	def uptime(self):
		return Formatter.ts_diff_to_str(self.start_time, datetime.now(), False)
