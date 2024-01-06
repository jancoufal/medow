import datetime
import logging
import sys
import time
import traceback
from typing import Dict

import youtube_dl.youtube_dl as youtube_dl
from mcontext import AppContext
from mtaskstate import TaskState, TaskStateEnum
from msource import sources
import mformatters


class _TaskBase(object):
	def __init__(self, ctx: AppContext, name: str):
		self.ctx = ctx
		self._l = ctx.logger.getChild("task")
		self.id = self.ctx.get_next_task_id()
		self.name = name
		self.start_time = datetime.datetime.now()

	def _update_task(self, title: str, state: TaskStateEnum):
		self._l.debug(f"Updating task {self.id} to {state}")
		self.ctx.state.update_task_state(TaskState(
			self.id,
			state,
			self.name,
			title,
			self.start_time,
			mformatters.ts_diff_to_str(self.start_time, datetime.datetime.now(), include_ms=False)
		))

	def on_new(self, description: str):
		self._update_task(description, TaskStateEnum.QUEUED)

	def on_start(self, description: str):
		self.start_time = datetime.datetime.now()
		self._update_task(description, TaskStateEnum.RUNNING)

	def on_progress(self, description: str):
		self._update_task(description, TaskStateEnum.RUNNING)

	def on_success(self, description: str):
		self._update_task(description, TaskStateEnum.FINISHED)

	def on_failure(self, description: str):
		self._update_task(description, TaskStateEnum.FAILED)


class TaskDummy(_TaskBase):
	def __init__(self, ctx: AppContext, name: str, description: str):
		super().__init__(ctx, name)
		self._description = description

	def __call__(self):
		self.on_start(f"Dummy task #{self.id} ({self._description}) started.")
		for p in range(10):
			time.sleep(1)
			self.on_progress(f"Dummy task #{self.id} ({self._description}) running - {p*10}% done.")
		self.on_success(f"Dummy task #{self.id} ({self._description}) finished.")


class TaskScrapSource(_TaskBase):
	def __init__(self, ctx: AppContext, source: sources.Source):
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
	def __init__(self, owning_task: "TaskYoutubeDownload"):
		self._owning_task = owning_task
		self._l = self._owning_task.ctx.logger.getChild("progress_hook")

	def __call__(self, info: Dict[str, str], *args, **kwargs):
		try:
			# status, downloaded_bytes, fragment_index, fragment_count, filename, tmpfilename, elapsed, total_bytes_estimate, speed, eta, _eta_str, _percent_str, _speed_str, _total_bytes_estimate_str
			# self._l.debug(f"Progress hook: {info=}, {args=}, {kwargs=}")
			self._owning_task.on_progress(
				f"{info.get('status', 'Downloading').title()}"
				f" file: '{info.get('filename', 'n/a')}'."
				f" eta: {info.get('_eta_str', 'n/a').strip()},"
				f" progress: {info.get('_percent_str', 'n/a').strip()},"
				f" speed: {info.get('_speed_str', 'n/a').strip()}"
			)
		except Exception as e:
			self._l.error(f"Exception {e}.")


class TaskYoutubeDownload(_TaskBase):
	def __init__(self, ctx: AppContext, url: str):
		super().__init__(ctx, "YouTube-DL")
		self._url = url
		self.on_new(f"Scrap task for video {self._url}' enqueued.")

	def __call__(self):
		self.on_start(f"Downloading of '{self._url}' is running.""")

		try:
			ydl_opts = {
				# "format": "bestvideo",
				"cachedir": False,
				"call_home": False,
				"no_color": True,
				"outtmpl": f"{self.ctx.config.storage.yt_dl}/%(title)s-%(id)s.%(ext)s",
				"logger": _YoutubeLogger(self.ctx.logger),
				"progress_hooks": [_YoutubeProgressHook(self)],
				"http_headers": {
					"User-Agent": "Mozilla/5.0",
					"Referer": self._url,
				},
			}

			self._l.info(f"Initiating download of '{self._url}'.")
			with youtube_dl.YoutubeDL(ydl_opts) as ydl:
				ydl.download([self._url])

			self._l.info(f"Download of '{self._url}' finished successfully.")
			self.on_success(f"Video '{self._url}' has been downloaded.")

		except Exception as ex:

			e = sys.exc_info()
			exception_info = {
				"exception": {
					"type": e[0],
					"value": e[1],
					"traceback": traceback.format_tb(e[2]),
				}
			}

			self._l.error(f"Download of '{self._url}' failed. Exception: {ex}, {exception_info=}.")
			self.on_failure(f"Video '{self._url}' has *not* been downloaded. Exception: {ex}, {exception_info=}.")
