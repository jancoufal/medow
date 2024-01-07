from dataclasses import dataclass, field
from dataclass_wizard import YAMLWizard
from typing import Dict


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
	sqlite_datafile: str


@dataclass
class ConfigRepositoryLimits:
	select_min: int
	select_max: int
	select_fallback: int


@dataclass
class ConfigStorage:
	source_static: str
	yt_dl: str


@dataclass
class ConfigLimits:
	images: int
	scraps: int


@dataclass
class ConfigScrapperSettings:
	base_url: str
	img_base: str
	href_needle: str
	url_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class Config(YAMLWizard):
	debug: bool
	site_title: str
	logging: ConfigLogging
	worker_thread: ConfigWorkerThread
	server: ConfigServer
	limits: ConfigLimits
	persistence: ConfigPersistence
	repository_limits: ConfigRepositoryLimits
	scrappers: Dict[str, ConfigScrapperSettings]
	storage: ConfigStorage
