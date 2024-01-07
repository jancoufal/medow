import logging
from dataclasses import dataclass

from flask import Flask

from mconfig import Config
from mstate import WebState
from mtaskprocessing import TaskProcessor


@dataclass
class AppContext(object):
	app: Flask
	logger: logging.Logger
	config: Config
	state: WebState
	task_processor: TaskProcessor

	@classmethod
	def create(cls, flask_app: Flask, config_file: str):

		config = Config.from_yaml_file(config_file)

		logging.basicConfig(
			format=config.logging.format,
			level=config.logging.level,
		)

		logger = logging.getLogger(config.logging.name)

		return cls(
			app=flask_app,
			logger=logger,
			config=config,
			state=WebState(),
			task_processor=TaskProcessor(logger.getChild("task_processor"), config.worker_thread),
		)
