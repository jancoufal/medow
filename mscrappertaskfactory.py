from time import sleep
from logging import Logger
from typing import Dict, Tuple, List
from pathlib import Path
from datetime import datetime
import urllib
import requests
from http import HTTPStatus
from ftplib import FTP_TLS, FTP


from youtube_dl.youtube_dl import YoutubeDL
import bs4

from mconfig import Config, ConfigScrapperRoumen, ConfigFtp
from mrepository import Repository
from mrepository_entities import TaskClassAndType, TaskClass, TaskType, MTaskItemE, TaskSyncStatusEnum
from mscrappers_api import TaskEvents, TaskEventDispatcher
from mscrappers_eventhandlers import TaskEventLogger, TaskEventRepositoryWriter
from mformatters import Formatter


class TaskFactory(object):
	def __init__(self, logger: Logger, config: Config, repository_persistent: Repository, repository_in_memory: Repository):
		self._logger = logger
		self._config = config
		self._repository_persistent = repository_persistent
		self._repository_in_memory = repository_in_memory

	def _create_event_handler(
			self,
			task_def: TaskClassAndType,
			success_task_sync_status: TaskSyncStatusEnum = TaskSyncStatusEnum.NOT_SYNCED
	):
		return TaskEventDispatcher((
			TaskEventLogger(self._logger.getChild("event"), task_def),
			TaskEventRepositoryWriter(self._repository_in_memory, task_def, success_task_sync_status),
			TaskEventRepositoryWriter(self._repository_persistent, task_def, success_task_sync_status),
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
			self._repository_persistent
		)

	def create_task_roumen_maso(self):
		task_def = TaskClassAndType(TaskClass.SCRAP, TaskType.ROUMEN_MASO)
		return TaskRoumen(
			self._create_event_handler(task_def),
			self._logger.getChild(str(task_def)),
			task_def,
			self._config.scrappers.roumen_maso,
			self._config.scrappers.storage_path,
			self._repository_persistent
		)

	def create_task_youtube_dl(self, urls: Tuple[str, ...]):
		task_def = TaskClassAndType(TaskClass.SCRAP, TaskType.YOUTUBE_DL)
		return TaskYoutubeDownload(
			self._create_event_handler(task_def),
			self._logger.getChild(str(task_def)),
			f"{self._config.scrappers.storage_path}",
			urls
		)

	def create_task_ftp_sync(self, task_type: TaskType):
		task_def = TaskClassAndType(TaskClass.SYNC, task_type)
		return SyncToFtp(
			self._create_event_handler(task_def, TaskSyncStatusEnum.IGNORE),
			self._logger.getChild(str(task_def)),
			task_def,
			self._repository_persistent,
			self._config.scrappers.storage_path,
			self._config.ftp
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
			storage_dir: str,
			repository: Repository
	):
		self._event = task_event_handler
		self._logger = logger
		self._task_def = task_def
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
					relative_path = Path(self._task_def.typ.value).joinpath(f"{ts:%Y}").joinpath(f"{ts:%V}")
					destination_path = self._storage_dir / relative_path

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
		get_result = requests.get(self._config_scrapper.base_url, params=self._config_scrapper.url_params)
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

	def warning(self, message: str):
		self._l.warning(message)

	def error(self, message: str):
		self._l.error(message)


class TaskYoutubeDownload(object):
	def __init__(self, task_event_handler: TaskEvents, yt_logger: Logger, storage_directory: str, urls: Tuple[str, ...]):
		self._event = task_event_handler
		self._yt_logger = yt_logger
		self._urls = [url.strip() for url in urls if len(url.strip()) > 0]
		self._storage_directory = storage_directory
		self._event.on_new()
		self._destination_path = None

	def __call__(self):
		ts = datetime.now()
		self._event.on_start()

		try:
			ydl_opts = {
				# "format": "bestvideo",
				"cachedir": False,
				"call_home": False,
				"no_color": True,
				"outtmpl": f"{self._storage_directory}{TaskType.YOUTUBE_DL.value}/{ts:%Y}/{ts:%V}/%(title)s-%(id)s.%(ext)s",
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

					self._event.on_item_finish(self._destination_path)

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

			if info.get("status", "-").lower() == "finished":
				self._destination_path = None

			if self._destination_path is None and info.get("filename", None) is not None:
				self._destination_path = info.get("filename").removeprefix(self._storage_directory)

		except Exception as ex:
			self._event.on_item_progress(f"Exception {ex}.")


"""
	SYNC TASK
"""


class SyncToFtp(object):
	def __init__(
			self,
			task_event_handler: TaskEvents,
			logger: Logger,
			task_def: TaskClassAndType,
			repository: Repository,
			storage_dir: str,
			ftp_config: ConfigFtp
	):
		self._event = task_event_handler
		self._logger = logger
		self._logger_ftp = logger.getChild("ftp")
		self._task_def = task_def
		self._repository = repository
		self._storage_dir = Path(storage_dir)
		self._ftp_config = ftp_config
		self._event.on_new()

	def __call__(self):
		self._event.on_start()
		try:
			with FTP_TLS(host=self._ftp_config.host, user=self._ftp_config.user, passwd=self._ftp_config.password) as ftp:
				for item_to_sync in self._repository.read_task_items_not_synced(self._task_def):
					self._item_sync(ftp, item_to_sync)
			self._event.on_finish()
		except Exception as ex:
			self._event.on_error(ex)

	def _item_sync(self, ftp: FTP, item: MTaskItemE):
		try:
			self._event.on_item_start(item.item_name, item.pk_id)
			self._logger_ftp.info(f"Changing directory to root.")
			ftp.cwd("/")

			# go to required directory (and create the directory structure if needed)
			lp = Path(item.destination_path)
			for path_dir in lp.parent.parts:
				if not len(list(filter(lambda r: r[0] == path_dir and r[1].get("type", "") == "dir", ftp.mlsd()))) > 0:
					self._logger_ftp.info(f"Creating directory '{path_dir}'.")
					ftp.mkd(path_dir)
				ftp.cwd(path_dir)
			self._logger_ftp.info(f"Directory changed to '{lp.parent}'.")

			with open(self._storage_dir / lp, "rb") as fp:
				ftp.storbinary("STOR " + lp.name, fp=fp, blocksize=self._ftp_config.blocksize)

			item.sync_status = TaskSyncStatusEnum.SYNCED.value
			self._repository.update_entity(item)

			self._event.on_item_finish(lp.name)

		except Exception as ex:
			self._event.on_item_error(ex)
