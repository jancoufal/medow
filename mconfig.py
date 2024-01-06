from dataclasses import dataclass
from pathlib import Path

from dataclass_binder import Binder


@dataclass
class ConfigLogging:
	name: str
	format: str
	level: int


@dataclass
class ConfigServer:
	host: str
	port: int


@dataclass
class ConfigWorkerThread:
	max_workers: int


@dataclass
class ConfigPersistence:
	sqlite_datafile: Path


@dataclass
class ConfigStorage:
	source_static: str
	yt_dl: str


@dataclass
class ConfigLimits:
	images: int
	scraps: int


@dataclass
class Config:
	debug: bool
	site_title: str
	logging: ConfigLogging
	worker_thread: ConfigWorkerThread
	server: ConfigServer
	limits: ConfigLimits
	persistence: ConfigPersistence
	storage: ConfigStorage

	@classmethod
	def from_file(cls, config_file: str) -> "Config":
		return Binder(Config).parse_toml(config_file)
