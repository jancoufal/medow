from time import sleep
from logging import Logger
from typing import Dict, Tuple

from youtube_dl.youtube_dl import YoutubeDL

from mconfig import Config
from mrepository import Repository
from mscrappers_api import ScrapperType, ScrapperEvents, ScrapperEventDispatcher
from mscrappers_eventhandlers import ScrapperEventLogger, ScrapperEventRepositoryWriter
from mformatters import Formatter


class TaskFactory(object):
	def __init__(self, logger: Logger, config: Config, repository_persistent: Repository, repository_in_memory: Repository):
		self._logger = logger
		self._config = config
		self._repository_persistent = repository_persistent
		self._repository_in_memory = repository_in_memory

	def _create_event_handler(self, scrapper_type: ScrapperType):
		return ScrapperEventDispatcher((
			ScrapperEventLogger(self._logger.getChild("event"), scrapper_type),
			ScrapperEventRepositoryWriter(self._repository_in_memory, scrapper_type),
			ScrapperEventRepositoryWriter(self._repository_persistent, scrapper_type),
		))

	def create_task_dummy(self, description: str):
		return _TaskDummy(self._create_event_handler(ScrapperType.DUMMY), description)

	def create_task_roumen_kecy(self):
		raise NotImplementedError  # TODO: implement

	def create_task_roumen_maso(self):
		raise NotImplementedError  # TODO: implement

	def create_task_youtube_dl(self, urls: Tuple[str, ...]):
		storage_directory = self._config.storage.yt_dl
		return TaskYoutubeDownload(
			self._create_event_handler(ScrapperType.YOUTUBE_DL),
			self._logger.getChild("yt_logger"),
			storage_directory,
			urls
		)


class _TaskDummy(object):
	def __init__(self, scrapper_event_handler: ScrapperEvents, description: str):
		self._event = scrapper_event_handler
		self._description = description
		self._event.on_new()

	def __call__(self):
		i_max, j_max = 10, 10
		self._event.on_start()
		for i in range(i_max):
			self._event.on_item_start(f"item '{self._description}' #{i+1} of #{i_max}")
			for j in range(j_max):
				sleep(.1)
				self._event.on_item_progress(f"item '{self._description}' #{i+1} progress: {Formatter.percentage_str(j+1, j_max)}")
			self._event.on_item_finish(None)
		self._event.on_finish()


"""
	YOUTUBE
"""


class _YoutubeLogger(object):
	def __init__(self, logger: Logger):
		self._l = logger.getChild("youtube_logger")

	def debug(self, message: str):
		self._l.debug(message)

	def warning(self, message: str):
		self._l.warning(message)

	def error(self, message: str):
		self._l.error(message)


class TaskYoutubeDownload(object):
	def __init__(self, scrapper_event_handler: ScrapperEvents, yt_logger: Logger, storage_directory: str, urls: Tuple[str, ...]):
		self._event = scrapper_event_handler
		yt_logger.debug(f"scrapper_event_handler: {scrapper_event_handler}")
		self._yt_logger = yt_logger
		self._urls = [url.strip() for url in urls if len(url.strip()) > 0]
		self._storage_directory = storage_directory
		self._event.on_new()

	def __call__(self):
		self._event.on_start()

		try:
			ydl_opts = {
				# "format": "bestvideo",
				"cachedir": False,
				"call_home": False,
				"no_color": True,
				"outtmpl": f"{self._storage_directory}/%(title)s-%(id)s.%(ext)s",
				"logger": _YoutubeLogger(self._yt_logger),
				"progress_hooks": [self._progress_hook],
				"http_headers": {
					"User-Agent": "Mozilla/5.0",
				},
			}

			for url in self._urls:
				try:
					self._event.on_item_start(url)

					with YoutubeDL(ydl_opts) as ydl:
						ydl.download([url])

					self._event.on_item_finish(None)  # TODO: local path

				except Exception as ex:
					self._event.on_item_error(ex)

			self._event.on_finish()

		except Exception as ex:
			self._event.on_error(ex)

	def _progress_hook(self, info: Dict[str, str], *args, **kwargs):
		try:
			# status, downloaded_bytes, fragment_index, fragment_count, filename, tmpfilename, elapsed, total_bytes_estimate, speed, eta, _eta_str, _percent_str, _speed_str, _total_bytes_estimate_str
			self._event.on_item_progress(
				f"{info.get('status', 'Downloading').title()}"
				f" file: '{info.get('filename', 'n/a')}'."
				f" eta: {info.get('_eta_str', 'n/a').strip()},"
				f" progress: {info.get('_percent_str', 'n/a').strip()},"
				f" speed: {info.get('_speed_str', 'n/a').strip()}"
			)
		except Exception as ex:
			self._event.on_item_progress(f"Exception {ex}.")
