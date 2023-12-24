from dataclasses import dataclass
from dataclass_binder import Binder
from pathlib import Path
from flask import Flask
import os


CONFIG_FILE: Path = Path("config.toml")
CONFIG = None
app = Flask(__name__)


@dataclass
class ConfigServer:
	host: str
	port: int


@dataclass
class ConfigPersistence:
	sqlite_datafile: Path


@dataclass
class Config:
	debug: bool
	server: ConfigServer
	persistence: ConfigPersistence


@app.route('/')
def hello_world():  # put application's code here
	sqldata_file = CONFIG.persistence.sqlite_datafile

	return f"<pre>Hello, {CONFIG};\n{os.path.exists(sqldata_file)=}</pre>"


if __name__ == "__main__":
	CONFIG = Binder(Config).parse_toml(CONFIG_FILE)

	print(CONFIG)

	if CONFIG.server.port is None:
		raise ValueError(f"Server port not specified in '{CONFIG_FILE}'")

	if CONFIG.debug:
		CONFIG.persistence.sqlite_datafile = Path(os.getcwd()) / CONFIG.persistence.sqlite_datafile

	app.run(
		host=CONFIG.server.host,
		port=CONFIG.server.port,
		debug=CONFIG.debug
	)
