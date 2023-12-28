import datetime

import scrappers
from mcontext import AppContext
from mtaskresult import TaskResult


class _TaskBase(object):
	def __init__(self, ctx: AppContext, name: str):
		self.ctx = ctx
		self.id = self.ctx.get_next_task_id()
		self.name = name
		self.start_time = datetime.datetime.now()

	def _update_task(self, title: str, is_error: bool):
		self.ctx.state.update_task_result(TaskResult(
			self.id,
			self.name,
			title,
			is_error,
			self.start_time,
			scrappers.util.formatters.ts_diff_to_str(self.start_time, datetime.datetime.now(), include_ms=False)
		))

	def reset_start_time(self):
		self.start_time = datetime.datetime.now()

	def on_new(self, description: str):
		self._update_task(description, False)

	def on_success(self, description: str):
		self._update_task(description, False)

	def on_failure(self, description: str):
		self._update_task(description, True)


class TaskScrapSource(_TaskBase):
	def __init__(self, ctx: AppContext, source: scrappers.Source):
		super().__init__(ctx, "IMG")
		self._source = source
		self.on_new(f"Scrap task for '{source.name}' enqueued.")

	def __call__(self):
		self.reset_start_time()
		self.ctx.logger.debug(f"Task 'TaskScrapSource' Started - {self._source}")
		self.ctx.state.increment_counter()
		self.ctx.logger.debug(f"Task 'TaskScrapSource' Finished - {self._source}")
		self.on_failure(f"Images from '{self._source.name}' has *not* been downloaded :(.",)


class TaskYoutubeDownload(_TaskBase):
	def __init__(self, ctx: AppContext, url: str):
		super().__init__(ctx, "YT-DL")
		self._url = url

	def __call__(self):
		self.reset_start_time()
		self.ctx.logger.debug(f"Task 'TaskYoutubeDownload' Started - {self._url}")
		self.ctx.state.increment_counter()
		self.ctx.logger.debug(f"Task 'TaskYoutubeDownload' Finished - {self._url}")
		self.on_success(f"Video '{self._url}' has been downloaded.")
