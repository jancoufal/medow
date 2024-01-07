from dataclasses import dataclass, field
from dataclass_wizard import YAMLWizard
from typing import Dict


@dataclass
class ConfigLogger:
	name: str
	format: str
	level: int


@dataclass
class ConfigServer:
	host: str
	port: int
	debug: bool


@dataclass
class ConfigPersistence:
	sqlite_datafile: str


@dataclass
class ConfigWorkerThread:
	max_workers: int


@dataclass
class ConfigRepositoryLimits:
	select_min: int
	select_max: int
	select_fallback: int


@dataclass
class ConfigListingLimits:
	images: int
	scraps: int


@dataclass
class ConfigStorage:
	source_static: str
	yt_dl: str


@dataclass
class ConfigScrapperSettings:
	base_url: str
	img_base: str
	href_needle: str
	url_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class Config(YAMLWizard):
	site_title: str
	logger: ConfigLogger
	server: ConfigServer
	persistence: ConfigPersistence
	repository_limits: ConfigRepositoryLimits
	listing_limits: ConfigListingLimits
	worker_thread: ConfigWorkerThread
	scrappers: Dict[str, ConfigScrapperSettings]
	storage: ConfigStorage
