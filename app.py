import os
import socket
import sys
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from logging import basicConfig, getLogger

import psutil
from apscheduler.triggers.base import BaseTrigger
from flask import Flask, url_for, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler

from appcode.mconfig import Config
from appcode.mformatters import Formatter
from appcode.mrepository import RepositorySqlite3
from appcode.mrepository_entities import TaskClassAndType, TaskClass, TaskType
from appcode.mscrappertaskfactory import TaskFactory
from appcode.msqlite_api import SqliteApi

CONFIG_FILE = "config.yaml"


class AppConfigKeys(Enum):
	APP = "MEDOW"
	LOGGER = "LOGGER"
	START_TIME = "START_TIME"
	DEBUG = "DEBUG"


class AppExtensionKeys(Enum):
	REPOSITORY = "REPOSITORY"
	TASK_FACTORY = "TASK_FACTORY"
	TASK_EXECUTOR = "TASK_EXECUTOR"


# the APP
app = Flask(__name__)

### APP CONFIG

# config values
_app_config: Config = Config.from_yaml_file(CONFIG_FILE)

# logging
basicConfig(
	format=_app_config.logger.format,
	level=_app_config.logger.level,
)
_logger = getLogger(_app_config.logger.name)

app.config.update({
	AppConfigKeys.APP: _app_config,
	AppConfigKeys.LOGGER: _logger,
	AppConfigKeys.START_TIME: datetime.now(),
	AppConfigKeys.DEBUG: _app_config.app_debug
})

### APP EXTENSIONS

_repository = RepositorySqlite3(
	_logger.getChild("repository"),
	SqliteApi(_logger.getChild("sqlite3"), _app_config.persistence.sqlite_datafile)
)

app.extensions.update({
	AppExtensionKeys.REPOSITORY: _repository,
	AppExtensionKeys.TASK_FACTORY: TaskFactory(
		_logger.getChild("task"),
		_app_config,
		_repository),
	AppExtensionKeys.TASK_EXECUTOR: ThreadPoolExecutor(
		max_workers=_app_config.worker_thread.max_workers
	),
})

# APP initialized


# scheduled task (auto scrap)
def _scrap_job():
	task_factory = app.extensions[AppExtensionKeys.TASK_FACTORY]
	task_executor = app.extensions[AppExtensionKeys.TASK_EXECUTOR]

	task_executor.submit(task_factory.create_task_roumen_kecy())
	task_executor.submit(task_factory.create_task_roumen_maso())

_scheduler = BackgroundScheduler(timezone="Europe/Amsterdam")
_scheduler.add_job(
	_scrap_job,
	"cron",
	minute="0",
	hour="6,18",
	coalesce=True,
	misfire_grace_time=60*60,
	max_instances=1,
	id="auto-scrap",
)
_scheduler.start()


class HtmlEntitySymbol(Enum):
	HOME = "&#x2302;" # home icon
	STATE = "&#x22f1;"  # "&#x225f;"
	SCRAP = "&#x21ca;"


class ViewSources(Enum):
	ROUMEN_KECY = "roumen-kecy"
	ROUMEN_MASO = "roumen-maso"


def get_page_data(page_values: dict = None):

	def _debug_hostname(suffix: str | None = None) -> str:
		try:
			return socket.gethostbyname(socket.gethostname() + suffix if suffix is not None else "")
		except socket.gaierror as e:
			return f"{e!s}"

	config = app.config[AppConfigKeys.APP]
	page_data = {
		"site": config.site_title,
		"head": {
			"less": url_for("static", filename="site.less"),
		},
		"page_values": page_values,
		"current": {
			"endpoint": None if request.endpoint is None else url_for(request.endpoint, **page_values if page_values is not None else {}),
			"image_dir": url_for("static", filename=config.scrappers.storage_path_for_static),
			"debug": app.config[AppConfigKeys.DEBUG],
		},
		"links": {
			"griffin": url_for("page_griffin"),
		},
		"navigation": [
			{"name": HtmlEntitySymbol.HOME.value, "href": url_for("page_index"), },
			{"name": HtmlEntitySymbol.STATE.value, "href": url_for("page_state"), },
			{"name": HtmlEntitySymbol.SCRAP.value, "href": url_for("page_scrap"), },
			{"name": "E", "href": url_for("page_throw_error"), },
		],
		"web_state": {
			"uptime": Formatter.ts_diff_to_str(app.config[AppConfigKeys.START_TIME], datetime.now(), False),
		},
	}

	if app.config[AppConfigKeys.DEBUG]:
		page_data.update({
			"network": {
				"hostname": socket.gethostname(),
				"socket.gethostbyname": _debug_hostname(),
				"socket.gethostbyname (local)": _debug_hostname(".local"),
			},
			"config": str(config),
		})

	for s in ViewSources:
		page_data["navigation"].append({"name": s.value, "href": url_for("page_view", view_source=s.value)})

	return page_data


@app.route("/")
def page_index():
	return render_template("home.html", page_data=get_page_data())


@app.route("/debug/", methods=["GET"])
def page_debug_switch():
	app.config[AppConfigKeys.DEBUG] = False if app.config[AppConfigKeys.DEBUG] else True
	return page_index()


@app.route("/griffin/")
def page_griffin():
	return render_template("griffin.html", page_data=get_page_data())


@app.route("/state/")
@app.route("/state/<int:task_id>/")
def page_state(task_id: int = None):
	page_data = get_page_data()

	try:
		repo = app.extensions[AppExtensionKeys.REPOSITORY]

		page_data["state"] = {
			"uptime": Formatter.ts_diff_to_str(app.config[AppConfigKeys.START_TIME], datetime.now(), False),
			"psutil": {
				"cpu_load": psutil.cpu_percent(0.1),
				"memory_percent": psutil.virtual_memory().percent,
				"disk_percent": psutil.disk_usage("/").percent,
			},
			"process": {
				"pid": os.getpid(),
			},
			"active_task_id": task_id,
			"python_version": sys.version,
		}

		if task_id is not None:
			task = repo.load_entity_task(task_id)
			page_data["state"].update({
				"page_view_mode": "task_detail",
				"task": task,
				"task_items": repo.read_task_items(task),
			})
		else:
			page_data["state"].update({
				"page_view_mode": "task_overview",
				"tasks": repo.read_recent_tasks_all(app.config[AppConfigKeys.APP].listing_limits.scraps),
				"task_detail_link_base": url_for("page_state"),
			})

		return render_template("state.html", page_data=page_data)
	except Exception as ex:
		return render_exception_page(ex, page_data)


@app.route("/scrap/", methods=["GET", "POST"])
def page_scrap():
	page_data = get_page_data()
	try:
		# debug
		page_data["request"] = {
			"method": request.method,
			"args": request.args,
			"form": request.form,
		}

		page_data["sources"] = list(ViewSources)
		tasks = []

		task_factory = app.extensions[AppExtensionKeys.TASK_FACTORY]
		task_executor = app.extensions[AppExtensionKeys.TASK_EXECUTOR]

		match request.method, request.form.get("form", None):
			case ("POST", "scrap"):
				if request.form.get(f"source-{ViewSources.ROUMEN_KECY.value}", None) is not None:
					tasks.append(task_factory.create_task_roumen_kecy())
				if request.form.get(f"source-{ViewSources.ROUMEN_MASO.value}", None) is not None:
					tasks.append(task_factory.create_task_roumen_maso())

			case ("POST", "yt_dl"):
				if request.form.get("url-list", None) is not None:
					urls = tuple(url.strip() for url in request.form.get("url-list", "").split())
					tasks.append(task_factory.create_task_youtube_dl(urls))

		for task in tasks:
			task_executor.submit(task)

	except Exception as ex:
		return render_exception_page(ex, page_data=page_data)

	return render_template("scrap.html", page_data=page_data)


@app.route("/view/<view_source>/")
def page_view(view_source: str):
	page_data = get_page_data({"view_source": view_source})
	try:
		task_def = TaskClassAndType(TaskClass.DUMMY, TaskType.DUMMY)

		match view_source:
			case ViewSources.ROUMEN_KECY.value: task_def = TaskClassAndType(TaskClass.SCRAP, TaskType.ROUMEN_KECY)
			case ViewSources.ROUMEN_MASO.value: task_def = TaskClassAndType(TaskClass.SCRAP, TaskType.ROUMEN_MASO)
			case _: raise ValueError(f"Invalid view type '{view_source}'.")

		config = app.config[AppConfigKeys.APP]
		repository = app.extensions[AppExtensionKeys.REPOSITORY]

		items = repository.read_recent_task_items(
			task_def,
			config.listing_limits.images
		)

		page_data.update({
			"base_path": url_for("static", filename=config.scrappers.storage_path_for_static),
			"task_items": [item for item in items if item.destination_path is not None]
		})

		return render_template("view.html", page_data=page_data)
	except Exception as ex:
		return render_exception_page(ex, page_data=page_data)


@app.route("/throw_error")
def page_throw_error():
	page_data = get_page_data()
	try:
		raise RuntimeError("I'm runtime error!")
	except RuntimeError as ex:
		return render_exception_page(ex, page_data=page_data)


@app.errorhandler(404)
def page_not_found(e):
	page_data = get_page_data()
	page_data["error"] = {
		"code": e.code,
		"name": e.name,
		"description": e.description,
	}
	# note that we set the 404 status explicitly
	return render_template('error.html', page_data=page_data), 404


def render_exception_page(ex: Exception, page_data: dict):
	page_data.update({
		"exception": {
			"endpoint": page_data["current"]["endpoint"],
			"type": ex.__class__.__name__,
			"value": str(ex),
			"traceback": traceback.format_exception(ex),
		}
	})
	return render_template("exception.html", page_data=page_data)


if __name__ == "__main__":
	# sanity test
	config = app.config[AppConfigKeys.APP]
	app.config[AppConfigKeys.LOGGER].info(f"Starting app {config.site_title} in DEVELOPMENT mode.")

	app.run(
		host=config.server.host,
		port=config.server.port,
		debug=config.server.debug
	)
