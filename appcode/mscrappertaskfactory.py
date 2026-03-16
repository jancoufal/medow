import urllib
from datetime import datetime
from http import HTTPStatus
from logging import Logger
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep
from typing import Any, Tuple, List

import bs4
import requests
from yt_dlp import YoutubeDL

from .mconfig import Config, ConfigScrapperRoumen, ConfigYoutubeDl
from .mformatters import Formatter
from .mrepository import Repository
from .mrepository_entities import TaskClassAndType, TaskClass, TaskType
from .mscrappers_api import TaskEvents, TaskEventDispatcher
from .mscrappers_eventhandlers import TaskEventLogger, TaskEventRepositoryWriter


class TaskFactory(object):
	def __init__(self, logger: Logger, config: Config, repository: Repository):
		self._logger = logger
		self._config = config
		self._repository = repository

	def _create_event_handler(self, task_def: TaskClassAndType):
		return TaskEventDispatcher((
			TaskEventLogger(self._logger.getChild("event"), task_def),
			TaskEventRepositoryWriter(self._repository, task_def),
		))

	def create_task_dummy(self, description: str):
		task_def = TaskClassAndType(TaskClass.DUMMY, TaskType.DUMMY)
		return _TaskDummy(self._create_event_handler(task_def), description)

	def create_task_roumen_kecy(self):
		task_def = TaskClassAndType(TaskClass.SCRAP, TaskType.ROUMEN_KECY)
		return TaskRoumen(
			self._create_event_handler(task_def),
			self._logger.getChild(str(task_def)),
			task_def,
			self._config.scrappers.roumen_kecy,
			self._config.scrappers.storage_path,
			self._repository
		)

	def create_task_roumen_maso(self):
		task_def = TaskClassAndType(TaskClass.SCRAP, TaskType.ROUMEN_MASO)
		return TaskRoumen(
			self._create_event_handler(task_def),
			self._logger.getChild(str(task_def)),
			task_def,
			self._config.scrappers.roumen_maso,
			self._config.scrappers.storage_path,
			self._repository
		)

	def create_task_youtube_dl(self, urls: Tuple[str, ...], cookies_text: str | None = None):
		task_def = TaskClassAndType(TaskClass.LEECH, TaskType.YOUTUBE_DL)
		return TaskYoutubeDownload(
			self._create_event_handler(task_def),
			self._logger.getChild(str(task_def)),
			task_def,
			self._config.scrappers.storage_path,
			self._config.youtube_dl,
			cookies_text,
			urls
		)


"""
	DUMMY
"""


class _TaskDummy(object):
	def __init__(self, scrapper_event_handler: TaskEvents, description: str):
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
	ROUMEN
"""


class TaskRoumen(object):

	RECENT_ITEMS_LIMIT = 5000  # how many recent items should be read (this images won't be downloaded again)

	REQUEST_HEADERS = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0",
	}

	def __init__(
			self,
			task_event_handler: TaskEvents,
			logger: Logger,
			task_def: TaskClassAndType,
			config_scrapper: ConfigScrapperRoumen,
			storage_base_path: Path,
			repository: Repository
	):
		self._event = task_event_handler
		self._logger = logger
		self._task_def = task_def
		self._config_scrapper = config_scrapper
		self._storage_base_path = storage_base_path
		self._repository = repository
		self._event.on_new()

	def __call__(self):
		self._event.on_start()
		try:
			ts = datetime.now()

			for image_name_to_download in self._get_image_names_to_download():
				try:
					self._event.on_item_start(image_name_to_download)

					# path will be like "{scrap_path}/{source}/{yyyy}/{week}/{image.jpg}"
					relative_path = Path(self._task_def.typ.value).joinpath(f"{ts:%Y}").joinpath(f"{ts:%V}")
					destination_path = self._storage_base_path / relative_path

					destination_path.mkdir(parents=True, exist_ok=True)
					relative_file_path = relative_path / image_name_to_download

					remote_file_url = f"{self._config_scrapper.img_base}/{image_name_to_download}"
					self._logger.debug(f"Downloading {remote_file_url!s} to {destination_path!s}...")
					r = requests.get(
						remote_file_url,
						stream=True,
						headers=TaskRoumen.REQUEST_HEADERS,
						timeout=self._config_scrapper.request_timeout_seconds
					)

					self._logger.debug(f"Request finished with status '{r.status_code}'.")
					if r.status_code != HTTPStatus.OK:
						raise RuntimeError(f"Unexpected status {r.status_code}: {r.text}.")

					self._logger.debug(f"Writing response content to file '{(destination_path / image_name_to_download)!s}'.")
					with open(str(destination_path / image_name_to_download), "wb") as fh:
						for chunk in r.iter_content(chunk_size=self._config_scrapper.request_chunk_size):
							if chunk:
								fh.write(chunk)

					self._logger.debug(f"File '{image_name_to_download}' scrapped successfully.")
					self._event.on_item_finish(str(relative_file_path))

				except Exception as ex:
					self._event.on_item_error(ex)

			self._event.on_finish()
		except Exception as ex:
			self._event.on_error(ex)

	def _get_image_names_to_download(self) -> List[str]:
		self._logger.debug(f"Reading recent task items for '{self._task_def}' task.")
		recent_items = self._repository.read_recent_task_items(self._task_def, TaskRoumen.RECENT_ITEMS_LIMIT)
		self._logger.debug(f"{len(recent_items)} recent items read.")
		recent_items_names = set(i.item_name for i in recent_items)
		self._logger.debug(f"{len(recent_items_names)} recent item names available.")
		remote_images = self._scrap_image_names_from_website()
		remote_images = [_ for _ in remote_images if _ not in recent_items_names]
		self._logger.debug(f"{len(remote_images)} remote images not scrapped yet.")

		self._logger.debug(f"Removing duplicate image names...")
		seen = set()
		seen_add = seen.add
		image_names_to_download = list(reversed([_ for _ in remote_images if not (_ in seen or seen_add(_))]))
		self._logger.debug(f"{len(image_names_to_download)} remote images to download.")
		return image_names_to_download

	""" mine all the image paths from website """
	def _scrap_image_names_from_website(self) -> List[str]:
		self._logger.debug(f"Requesting page '{self._config_scrapper.base_url}' for images.")
		get_result = requests.get(
			self._config_scrapper.base_url,
			params=self._config_scrapper.url_params,
			timeout=self._config_scrapper.request_timeout_seconds
		)
		self._logger.debug(f"'{self._config_scrapper.base_url}' result code: '{get_result.status_code}'.")
		soup = bs4.BeautifulSoup(get_result.content.decode(get_result.apparent_encoding), features="html.parser")

		# extract all "a" tags having "roumingShow.php" present in the "href"
		self._logger.debug(f"Extracting links from the page.")
		all_urls = map(lambda a: urllib.parse.urlparse(a.get("href")), soup.find_all("a"))
		all_show = [url for url in all_urls if isinstance(url.path, str) and self._config_scrapper.href_needle in url.path]
		self._logger.debug(f"{len(all_show)} links extracted.")

		# extract all "file" values from the query string
		self._logger.debug(f"Extracing image names...")
		all_qstr = [urllib.parse.parse_qs(url.query) for url in all_show]
		all_imgs = [qs.get("file").pop() for qs in all_qstr if "file" in qs]
		self._logger.debug(f"{len(all_imgs)} image names extracted.")

		return all_imgs


"""
	YOUTUBE
"""


class _YoutubeLogger(object):
	def __init__(self, logger: Logger):
		self._l = logger.getChild("youtube_logger")

	def debug(self, message: str):
		self._l.debug(message)

	def info(self, message: str):
		self._l.info(message)

	def warning(self, message: str):
		self._l.warning(message)

	def error(self, message: str):
		self._l.error(message)


class TaskYoutubeDownload(object):
	def __init__(
			self,
			task_event_handler: TaskEvents,
			logger: Logger,
			task_def: TaskClassAndType,
			storage_base_path: Path,
			config_youtube_dl: ConfigYoutubeDl,
			cookies_text: str | None,
			urls: Tuple[str, ...]
	):
		self._event = task_event_handler
		self._logger = logger
		self._task_def = task_def
		self._storage_base_path = storage_base_path
		self._config_youtube_dl = config_youtube_dl
		self._cookies_text = cookies_text
		self._urls = tuple(url.strip() for url in urls if len(url.strip()) > 0)
		self._relative_directory = None
		self._destination_path = None
		self._event.on_new()

	def __call__(self):
		ts = datetime.now()
		self._event.on_start()

		try:
			self._relative_directory = Path(self._task_def.typ.value).joinpath(f"{ts:%Y}").joinpath(f"{ts:%V}")
			destination_directory = self._storage_base_path / self._relative_directory
			destination_directory.mkdir(parents=True, exist_ok=True)
			runtime_cookie_file = self._create_runtime_cookie_file(destination_directory)

			try:
				for url in self._urls:
					try:
						self._destination_path = None
						self._event.on_item_start(url)

						with YoutubeDL(self._create_ydl_options(destination_directory, runtime_cookie_file)) as ydl:
							info = ydl.extract_info(url, download=True)

							if self._destination_path is None:
								self._destination_path = self._extract_relative_destination_path(ydl, info)

						if self._destination_path is None:
							raise RuntimeError(f"Could not determine destination path for '{url}'.")
						self._event.on_item_finish(self._destination_path)

					except Exception as ex:
						self._event.on_item_error(ex)
			finally:
				if runtime_cookie_file is not None:
					try:
						Path(runtime_cookie_file).unlink()
					except Exception as ex:
						self._logger.warning(f"Could not remove temporary cookie file '{runtime_cookie_file}': {ex!s}")

			self._event.on_finish()

		except Exception as ex:
			self._event.on_error(ex)

	def _create_ydl_options(self, destination_directory: Path, runtime_cookie_file: str | None) -> dict[str, Any]:
		options = {
			"cachedir": False,
			"noplaylist": True,
			"nopart": True,
			"restrictfilenames": True,
			"no_color": True,
			"logger": _YoutubeLogger(self._logger),
			"progress_hooks": [self._progress_hook],
			# Prefer separate video+audio streams and fall back to a combined stream.
			# Using plain "best" is too strict and often fails on modern YouTube manifests.
			"format": "bv*+ba/b",
			"extractor_args": {
				"youtube": {
					# Avoid creator-specific client path that tends to trigger challenge issues.
					"player_client": ["android", "web"],
				}
			},
			"outtmpl": str(destination_directory / "%(title)s-%(id)s.%(ext)s"),
		}

		if runtime_cookie_file is not None:
			options["cookiefile"] = runtime_cookie_file
		elif self._config_youtube_dl.cookies_file is not None and len(self._config_youtube_dl.cookies_file.strip()) > 0:
			options["cookiefile"] = self._config_youtube_dl.cookies_file

		if "cookiefile" not in options and self._config_youtube_dl.cookies_from_browser is not None and len(self._config_youtube_dl.cookies_from_browser.strip()) > 0:
			# yt-dlp expects a tuple in python API mode.
			options["cookiesfrombrowser"] = (self._config_youtube_dl.cookies_from_browser.strip(),)

		return options

	def _create_runtime_cookie_file(self, destination_directory: Path) -> str | None:
		if self._cookies_text is None or len(self._cookies_text.strip()) == 0:
			return None

		cookies_text = self._cookies_text.strip()
		if not cookies_text.endswith("\n"):
			cookies_text += "\n"

		with NamedTemporaryFile(
			mode="w",
			encoding="utf-8",
			dir=str(destination_directory),
			prefix="yt-dlp-cookies-",
			suffix=".txt",
			delete=False
		) as tmp:
			tmp.write(cookies_text)
			return tmp.name

	def _progress_hook(self, info: dict[str, Any], *args, **kwargs):
		try:
			self._event.on_item_progress(
				f"{info.get('status', 'Downloading').title()}"
				f" file: '{info.get('filename', 'n/a')}'."
				f" eta: {info.get('_eta_str', 'n/a').strip()},"
				f" progress: {info.get('_percent_str', 'n/a').strip()},"
				f" speed: {info.get('_speed_str', 'n/a').strip()}"
			)

			filename = info.get("filename", None)
			if self._destination_path is None and isinstance(filename, str):
				self._destination_path = self._to_relative_destination_path(Path(filename))

		except Exception as ex:
			self._event.on_item_progress(f"Exception {ex}.")

	def _extract_relative_destination_path(self, ydl: YoutubeDL, info: dict[str, Any]) -> str | None:
		candidate_paths = []

		requested_downloads = info.get("requested_downloads", [])
		if isinstance(requested_downloads, list):
			for requested_download in requested_downloads:
				if isinstance(requested_download, dict):
					candidate_paths.append(requested_download.get("filepath"))

		candidate_paths.extend([
			info.get("filepath"),
			info.get("_filename"),
		])

		try:
			candidate_paths.append(ydl.prepare_filename(info))
		except Exception:
			pass

		for candidate_path in candidate_paths:
			if isinstance(candidate_path, str) and len(candidate_path) > 0:
				return self._to_relative_destination_path(Path(candidate_path))

		return None

	def _to_relative_destination_path(self, destination_path: Path) -> str:
		try:
			return str(destination_path.relative_to(self._storage_base_path))
		except ValueError:
			return str(self._relative_directory / destination_path.name)
