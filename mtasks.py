import datetime
import logging
import sys
import time
import traceback

import youtube_dl

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


class _YoutubeLogger(object):
	def __init__(self, logger: logging.Logger):
		self._l = logger.getChild("youtube_logger")

	def debug(self, message: str):
		self._l.debug(message)

	def warning(self, message: str):
		self._l.warning(message)

	def error(self, message: str):
		self._l.error(message)


class _YoutubeProgressHook(object):
	def __init__(self, logger: logging.Logger):
		self._l = logger.getChild("progress_hook")

	def __call__(self, *args, **kwargs):
		self._l.debug(f"Progress hook: {args=} {kwargs=}")


class TaskYoutubeDownload(_TaskBase):
	def __init__(self, ctx: AppContext, url: str):
		super().__init__(ctx, "YouTube-DL")
		self._url = url
		self.on_new(f"Scrap task for video {self._url}' enqueued.")

	def __call__(self):
		self.on_start(f"Downloading '{self._url}' is running.""")

		try:
			ydl_opts = {
				"format": "bestaudio/best",
				"cachedir": False,
				"call_home": True,
				"no_color": True,
				"download_archive": self.ctx.config.storage.yt_dl,
				"logger": _YoutubeLogger(self.ctx.logger),
				"progress_hooks": [_YoutubeProgressHook(self.ctx.logger)]
			}

			with youtube_dl.YoutubeDL(ydl_opts) as ydl:
				ydl.download([self._url])

			self.on_success(f"Video '{self._url}' has been downloaded.")

		except youtube_dl.utils.YoutubeDLError as ex:

			e = sys.exc_info()
			exception_info = {
				"exception": {
					"type": e[0],
					"value": e[1],
					"traceback": traceback.format_tb(e[2]),
				}
			}

			self.on_failure(f"Video '{self._url}' has *not* been downloaded. Exception: {ex}, {exception_info=}.")

