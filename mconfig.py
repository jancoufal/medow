from dataclasses import dataclass
from pathlib import Path
from typing import List

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
class ConfigLimits:
	images: int
	scraps: int


@dataclass
class ConfigAuth:
	key: str
	error_messages: List[str]


@dataclass
class Config:
	debug: bool
	site_title: str
	logging: ConfigLogging
	worker_thread: ConfigWorkerThread
	server: ConfigServer
	limits: ConfigLimits
	auth: ConfigAuth
	persistence: ConfigPersistence

	@classmethod
	def from_file(cls, config_file: str) -> "Config":
		return Binder(Config).parse_toml(config_file)
