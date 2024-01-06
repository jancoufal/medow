from typing import Dict, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from logging import Logger
import sys
import traceback
import time

from mconfig import ConfigWorkerThread
from mformatters import Formatter
from mscrapsources import ScrapSource
import youtube_dl.youtube_dl as youtube_dl


class TaskProcessor(object):
	def __init__(self, logger: Logger, config: ConfigWorkerThread):
		self._l = logger
		self._persistence = None  # TODO: persistence (sql)
		self._executor = ThreadPoolExecutor(max_workers=config.max_workers)
		self._task_sequence = 0
		self._task_states: Dict[int, TaskState] = {}  # key = task id

	def _get_next_task_id(self):
		_id = self._task_sequence
		self._task_sequence += 1
		return _id

	def _update_task_state(self, task_state: "TaskState"):
		self._task_states[task_state.id] = task_state

	def get_task_state_map(self):
		return self._task_states

	def create_and_process_new_task_dummy(self, name: str, description: str) -> "TaskDummy":
		task = TaskDummy(
			logger=self._l.getChild("task"),
			task_id=self._get_next_task_id(),
			update_task_callback=self._update_task_state,
			name=name,
			description=description,
		)

		self._executor.submit(task)

		return task

	def create_and_process_new_task_for_source(self, scrap_source: ScrapSource) -> "TaskScrapSource":
		task = TaskScrapSource(
			logger=self._l.getChild("task"),
			task_id=self._get_next_task_id(),
			update_task_callback=self._update_task_state,
			scrap_source=scrap_source,
		)

		self._executor.submit(task)

		return task

	def create_and_process_new_task_for_youtube_dl(self, url: str) -> "TaskYoutubeDownload":
		task = TaskYoutubeDownload(
			logger=self._l.getChild("task"),
			task_id=self._get_next_task_id(),
			update_task_callback=self._update_task_state,
			url=url,
		)

		self._executor.submit(task)

		return task


class TaskStateEnum(Enum):
	QUEUED = "queued"
	RUNNING = "running"
	FINISHED = "finished"
	FAILED = "failed"


@dataclass
class TaskState(object):
	id: int
	state: TaskStateEnum
	name: str
	result: str
	start_time: datetime
	time_taken: str

	@property
	def age(self):
		return Formatter.ts_diff_to_str(self.start_time, datetime.now(), False)


class _TaskBase(object):
	def __init__(self, logger: Logger, task_id: int, name: str, update_task_callback: Callable[[TaskState], None]):
		self._l = logger
		self.id = task_id
		self.name = name
		self._update_task_callback = update_task_callback
		self.start_time = datetime.now()

	def _update_task(self, title: str, state: TaskStateEnum):
		self._l.debug(f"Updating task {self.id} to {state}")
		self._update_task_callback(TaskState(
			self.id,
			state,
			self.name,
			title,
			self.start_time,
			Formatter.ts_diff_to_str(self.start_time, datetime.now(), include_ms=False)
		))

	def on_new(self, description: str):
		self._update_task(description, TaskStateEnum.QUEUED)

	def on_start(self, description: str):
		self.start_time = datetime.now()
		self._update_task(description, TaskStateEnum.RUNNING)

	def on_progress(self, description: str):
		self._update_task(description, TaskStateEnum.RUNNING)

	def on_success(self, description: str):
		self._update_task(description, TaskStateEnum.FINISHED)

	def on_failure(self, description: str):
		self._update_task(description, TaskStateEnum.FAILED)


class TaskDummy(_TaskBase):
	def __init__(self, logger: Logger, task_id: int, update_task_callback: Callable[[TaskState], None], name: str, description: str):
		super().__init__(logger, task_id, name, update_task_callback)
		self._description = description

	def __call__(self):
		self.on_start(f"Dummy task #{self.id} ({self._description}) started.")
		for p in range(10):
			time.sleep(1)
			self.on_progress(f"Dummy task #{self.id} ({self._description}) running - {p*10}% done.")
		self.on_success(f"Dummy task #{self.id} ({self._description}) finished.")


class TaskScrapSource(_TaskBase):
	def __init__(self, logger: Logger, task_id: int, update_task_callback: Callable[[TaskState], None], scrap_source: ScrapSource):
		super().__init__(logger, task_id, scrap_source.name, update_task_callback)
		self._source = scrap_source
		self.on_new(f"Scrap task for '{self._source.value}' enqueued.")

	def __call__(self):
		self.on_start(f"Scrap from '{self._source.value}' is running.")
		time.sleep(2)
		self.on_failure(f"Images from '{self._source.value}' has *not* been downloaded :(.")


class _YoutubeLogger(object):
	def __init__(self, logger: Logger):
		self._l = logger.getChild("youtube_logger")

	def debug(self, message: str):
		self._l.debug(message)

	def warning(self, message: str):
		self._l.warning(message)

	def error(self, message: str):
		self._l.error(message)


class _YoutubeProgressHook(object):
	def __init__(self, progress_logger: Logger, owning_task: "TaskYoutubeDownload"):
		self._l = progress_logger
		self._owning_task = owning_task

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
	def __init__(self, logger: Logger, task_id: int, update_task_callback: Callable[[TaskState], None], url: str):
		super().__init__(logger, task_id, "YouTube-DL", update_task_callback)
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
				"logger": _YoutubeLogger(self._l.getChild("yt_logger")),
				"progress_hooks": [_YoutubeProgressHook(self._l.getChild("yt_logger"), self)],
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
