from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from dataclass_wizard import YAMLWizard


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
class ConfigScrapperRoumen:
	request_timeout_seconds: int
	request_chunk_size: int
	base_url: str
	img_base: str
	href_needle: str
	url_params: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConfigScrappers:
	storage_path: Path
	storage_path_for_static: Path
	roumen_kecy: ConfigScrapperRoumen
	roumen_maso: ConfigScrapperRoumen


@dataclass
class Config(YAMLWizard):
	site_title: str
	app_debug: bool
	logger: ConfigLogger
	server: ConfigServer
	persistence: ConfigPersistence
	repository_limits: ConfigRepositoryLimits
	listing_limits: ConfigListingLimits
	worker_thread: ConfigWorkerThread
	scrappers: ConfigScrappers
