from time import sleep
from logging import Logger
from typing import Dict, Tuple, List
from pathlib import Path
from datetime import datetime
import urllib
import requests


from youtube_dl.youtube_dl import YoutubeDL
import bs4

from mconfig import Config, ConfigScrapperRoumen
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
		scrapper_type = ScrapperType.ROUMEN_KECY
		return TaskRoumen(
			self._create_event_handler(scrapper_type),
			self._logger.getChild(scrapper_type.value),
			scrapper_type,
			self._config.scrappers.roumen_kecy,
			self._config.scrappers.storage_path,
			self._repository_persistent
		)

	def create_task_roumen_maso(self):
		scrapper_type = ScrapperType.ROUMEN_MASO
		return TaskRoumen(
			self._create_event_handler(scrapper_type),
			self._logger.getChild(scrapper_type.value),
			scrapper_type,
			self._config.scrappers.roumen_maso,
			self._config.scrappers.storage_path,
			self._repository_persistent
		)

	def create_task_youtube_dl(self, urls: Tuple[str, ...]):
		scrapper_type = ScrapperType.YOUTUBE_DL
		return TaskYoutubeDownload(
			self._create_event_handler(scrapper_type),
			self._logger.getChild(scrapper_type.value),
			f"{self._config.scrappers.storage_path}yt_dl/",
			urls
		)


"""
	DUMMY
"""


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
	ROUMEN
"""


class TaskRoumen(object):

	RECENT_ITEMS_LIMIT = 1000  # how many recent items should be read (this images won't be downloaded again)

	REQUEST_HEADERS = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0",
	}

	def __init__(
			self,
			scrapper_event_handler: ScrapperEvents,
			logger: Logger,
			scrapper_type: ScrapperType,
			config_scrapper: ConfigScrapperRoumen,
			storage_dir: str,
			repository: Repository
	):
		self._event = scrapper_event_handler
		self._logger = logger
		self._scrapper_type = scrapper_type
		self._config_scrapper = config_scrapper
		self._storage_dir = storage_dir
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
					relative_path = Path(self._scrapper_type.value).joinpath(f"{ts:%Y}").joinpath(f"{ts:%V}")
					destination_path = self._storage_dir / relative_path

					destination_path.mkdir(parents=True, exist_ok=True)
					relative_file_path = relative_path / image_name_to_download

					remote_file_url = f"{self._config_scrapper.img_base}/{image_name_to_download}"
					# r = requests.get(remote_file_url, headers=TaskRoumen.REQUEST_HEADERS)
					urllib.request.urlretrieve(remote_file_url, filename=str(destination_path / image_name_to_download))

					self._event.on_item_finish(str(relative_file_path))

				except Exception as ex:
					self._event.on_item_error(ex)

			self._event.on_finish()
		except Exception as ex:
			self._event.on_error(ex)

	def _get_image_names_to_download(self) -> List[str]:
		recent_items = self._repository.read_recent_scrap_task_items(self._scrapper_type, TaskRoumen.RECENT_ITEMS_LIMIT)
		recent_items_names = set(i.item_name for i in recent_items)
		remote_images = self._scrap_image_names_from_website()
		remote_images = [_ for _ in remote_images if _ not in recent_items_names]

		# remove possible duplicates with preserved order and then reverse, because the "top" image should be scrapped last
		seen = set()
		seen_add = seen.add
		return list(reversed([_ for _ in remote_images if not (_ in seen or seen_add(_))]))

	""" mine all the image paths from website """
	def _scrap_image_names_from_website(self) -> List[str]:
		get_result = requests.get(self._config_scrapper.base_url, params=self._config_scrapper.url_params)
		soup = bs4.BeautifulSoup(get_result.content.decode(get_result.apparent_encoding), features="html.parser")

		# extract all "a" tags having "roumingShow.php" present in the "href"
		all_urls = map(lambda a: urllib.parse.urlparse(a.get("href")), soup.find_all("a"))
		all_show = [url for url in all_urls if isinstance(url.path,str) and self._config_scrapper.href_needle in url.path]

		# extract all "file" values from the query string
		all_qstr = [urllib.parse.parse_qs(url.query) for url in all_show]
		all_imgs = [qs.get("file").pop() for qs in all_qstr if "file" in qs]

		return all_imgs



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
