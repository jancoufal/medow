from dataclasses import dataclass
from logging import Logger, basicConfig, getLogger
from typing import Callable

from flask import Flask

from mconfig import Config
from mrepository import Repository
from mrepository_installer import RepositoryInstaller
from mscrappertaskfactory import TaskFactory
from msqlite_api import SqliteApi
from mtaskprocessing import TaskProcessor


@dataclass
class AppContext(object):
	app: Flask
	logger: Logger
	config: Config
	repository_persistent: Repository
	repository_in_memory: Repository
	task_factory: TaskFactory
	task_processor: TaskProcessor

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

		def create_repository(repository_logger: Logger, creator: Callable[[Logger], SqliteApi]) -> Repository:
			repository_logger.info(f"Creating repository.")
			return Repository(repository_logger.getChild("repository"), creator(repository_logger.getChild("sqlapi")))

		repository_persistent = create_repository(
			logger.getChild("persistent"),
			lambda _logger: SqliteApi.create_persistent(_logger, config.persistence.sqlite_datafile)
		)

		repository_in_memory = create_repository(
			logger.getChild("in_memory"),
			lambda _logger: SqliteApi.create_in_memory(_logger)
		)

		logger.info(f"Creating tables in in-memory repository.")
		RepositoryInstaller(repository_in_memory).create_tables()

		return cls(
			app=flask_app,
			logger=logger,
			config=config,
			repository_persistent=repository_persistent,
			repository_in_memory=repository_in_memory,
			task_factory=TaskFactory(logger.getChild("task"), config, repository_persistent, repository_in_memory),
			task_processor=TaskProcessor(logger.getChild("queue"), config.worker_thread),
		)
