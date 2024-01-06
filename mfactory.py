from mconfig import Config
from mcontext import AppContext
# from mtasks import TaskDummy, TaskScrapSource, TaskYoutubeDownload


class AllFactory(object):
	def __init__(self, config: Config):
		self._config = config

	def create_task_dummy(self, ctx: AppContext, name: str, description: str):
		pass
