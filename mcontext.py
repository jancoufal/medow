import concurrent.futures
import logging
from dataclasses import dataclass

from flask import Flask

import mconfig
import mstate


@dataclass
class AppContext(object):
	app: Flask
	logger: logging.Logger
	config: mconfig.Config
	state: mstate.WebState
	next_task_id: int
	task_executor: concurrent.futures.ThreadPoolExecutor

	def get_next_task_id(self):
		_id = self.next_task_id
		self.next_task_id += 1
		return _id
