import sys, typing, traceback
import datetime, os, pathlib
import requests, urllib, bs4
import sqlite3
from ..sources import Source
from ..settings import Settings
from ..result import Result, ResultItem, ExceptionInfo
from ..database import DbScrapWriter, DbScrapReader


class _RoumenSettings(object):
	def __init__(self, base_url: str, base_url_params: dict, img_base: str, href_needle: str):
		self.base_url = base_url
		self.base_url_params = base_url_params
		self.img_base = img_base
		self.href_needle = href_needle


class BaseRoumen(object):

	REQUEST_HEADERS = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0",
	}

	def __init__(self, source: Source, settings: Settings, roumen_settings: _RoumenSettings):
		self._settings = settings
		self._source = source
		self._roumen_settings = roumen_settings

	def scrap(self):
		ts = datetime.datetime.now()
		result = Result(self._source, ts)
		scrap_writer = DbScrapWriter.create(self._settings.sqlite_datafile, self._source)

		try:
			for image_to_download in self._get_images_to_download():
				# path will be like "{scrap_path}/{source}/{yyyy}/{week}/{image.jpg}"
				relative_path = pathlib.Path(self._source.value).joinpath(f"{ts:%Y}").joinpath(f"{ts:%V}")
				destination_path = self._settings.scrap_path / relative_path

				try:
					destination_path.mkdir(parents=True, exist_ok=True)
					relative_file_path = relative_path / image_to_download

					remote_file_url = f"{self._roumen_settings.img_base}/{image_to_download}"
					# r = requests.get(remote_file_url, headers=Roumen.REQUEST_HEADERS)
					urllib.request.urlretrieve(remote_file_url, filename=str(destination_path / image_to_download))

					result.on_item(ResultItem.createSucceeded(relative_file_path, remote_file_url))
					scrap_writer.on_scrap_item_success(relative_file_path, image_to_download)

				except:
					e_info = ExceptionInfo.createFromLastException()
					result.on_item(ResultItem.createFailed(image_to_download, e_info))
					scrap_writer.on_scrap_item_failure(item_name=image_to_download, description="scrap failure", exception_info=e_info)

			scrap_writer.finish()

		except:
			e_info = ExceptionInfo.createFromLastException()
			result.on_scrapping_exception(e_info)
			scrap_writer.finish_exceptionaly(e_info)

		finally:
			result.on_scrapping_finished()

		return result

	def _get_images_to_download(self):
		remote_image_names = self._scrap_image_names()
		stored_image_names = DbScrapReader.create(self._settings.sqlite_datafile, self._source).read_recent_item_names()
		images_to_download = [name for name in remote_image_names if name not in stored_image_names]

		# remove possible duplicates with preserved order and then reverse, because the "top" image should be scrapped last
		seen = set()
		seen_add = seen.add
		return reversed([_ for _ in images_to_download if not (_ in seen or seen_add(_))])

	def _scrap_image_names(self):
		r = requests.get(self._roumen_settings.base_url, params=self._roumen_settings.base_url_params)
		soup = bs4.BeautifulSoup(r.content.decode(r.apparent_encoding), features="html.parser")

		# extract all "a" tags having "roumingShow.php" present in the "href"
		all_urls = map(lambda a: urllib.parse.urlparse(a.get("href")), soup.find_all("a"))
		all_show = [url for url in all_urls if isinstance(url.path,str) and self._roumen_settings.href_needle in url.path]

		# extract all "file" values from the query string
		all_qstr = [urllib.parse.parse_qs(url.query) for url in all_show]
		all_imgs = [qs.get("file").pop() for qs in all_qstr if "file" in qs]

		return all_imgs


class Roumen(BaseRoumen):
	def __init__(self, settings: Settings):
		super().__init__(Source.ROUMEN, settings, _RoumenSettings(
			base_url="https://www.rouming.cz",
			base_url_params={},
			img_base="https://www.rouming.cz/upload",
			href_needle="roumingShow.php"
		))

class RoumenMaso(BaseRoumen):
	def __init__(self, settings: Settings):
		super().__init__(Source.ROUMEN_MASO, settings, _RoumenSettings(
			base_url="https://www.roumenovomaso.cz",
			base_url_params={"agree":"on"},
			img_base="https://www.roumenovomaso.cz/upload",
			href_needle="masoShow.php"
		))
