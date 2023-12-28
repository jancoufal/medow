import datetime
import time

import scrappers
from mcontext import AppContext
from mtaskstate import TaskState, TaskStateEnum


class _TaskBase(object):
	def __init__(self, ctx: AppContext, name: str):
		self.ctx = ctx
		self.id = self.ctx.get_next_task_id()
		self.name = name
		self.start_time = datetime.datetime.now()

	def _update_task(self, title: str, state: TaskStateEnum):
		self.ctx.state.update_task_state(TaskState(
			self.id,
			state,
			self.name,
			title,
			self.start_time,
			scrappers.util.formatters.ts_diff_to_str(self.start_time, datetime.datetime.now(), include_ms=False)
		))

	def on_new(self, description: str):
		self._update_task(description, TaskStateEnum.QUEUED)

	def on_start(self, description: str):
		self.start_time = datetime.datetime.now()
		self._update_task(description, TaskStateEnum.RUNNING)

	def on_success(self, description: str):
		self._update_task(description, TaskStateEnum.FINISHED)

	def on_failure(self, description: str):
		self._update_task(description, TaskStateEnum.FAILED)


class TaskScrapSource(_TaskBase):
	def __init__(self, ctx: AppContext, source: scrappers.Source):
		super().__init__(ctx, source.name)
		self._source = source
		self.on_new(f"Scrap task for '{self._source.value}' enqueued.")

	def __call__(self):
		self.on_start(f"Scrap from '{self._source.value}' is running.")
		time.sleep(2)
		self.on_failure(f"Images from '{self._source.value}' has *not* been downloaded :(.")


class TaskYoutubeDownload(_TaskBase):
	def __init__(self, ctx: AppContext, url: str):
		super().__init__(ctx, "YouTube-DL")
		self._url = url
		self.on_new(f"Scrap task for video {self._url}' enqueued.")

	def __call__(self):
		self.on_start(f"Downloading '{self._url}' is running.""")
		time.sleep(2)
		self.on_success(f"Video '{self._url}' has been downloaded.")
