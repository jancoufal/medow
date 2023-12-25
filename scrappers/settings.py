import typing
import pathlib


class Settings(object):
	def __init__(self, local_base_path: pathlib.Path, local_relative_path: pathlib.Path, sqlite_datafile: pathlib.Path):
		self._base_path = local_base_path
		self._relative_path = local_relative_path
		self._sqlite_datafile = sqlite_datafile

	@property
	def base_path(self):
		return self._base_path

	@property
	def relative_path(self):
		return self._relative_path

	@property
	def scrap_path(self):
		return self._base_path / self._relative_path

	@property
	def sqlite_datafile(self):
		return self._sqlite_datafile
