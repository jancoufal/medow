import os
import socket
import sys
import traceback
import psutil
from enum import Enum

from flask import Flask, url_for, render_template, request

import menvloader
from mcontext import AppContext
from mrepository import RepositoryType
from mrepository_entities import TaskClassAndType, TaskClass, TaskType

CONFIG_FILE = "config.yaml"
app = Flask(__name__)
app.ctx = None


class HtmlEntitySymbol(Enum):
	HOME = "&#x2302;"
	STATE = "&#x22f1;"  # "&#x225f;"
	SCRAP = "&#x21ca;"


class ViewSources(Enum):
	ROUMEN_KECY = "roumen-kecy"
	ROUMEN_MASO = "roumen-maso"


def get_app_context() -> AppContext:
	global app
	return app.ctx


def get_page_data(page_values: dict = None):
	app_context = get_app_context()
	page_data = {
		"site": app_context.config.site_title,
		"head": {
			"less": url_for("static", filename="site.less"),
		},
		"page_values": page_values,
		"current": {
			"endpoint": None if request.endpoint is None else url_for(request.endpoint, **page_values if page_values is not None else {}),
			"image_dir": url_for("static", filename=app_context.config.scrappers.storage_path_for_static),
			"debug": app_context.config.app_debug,
		},
		"links": {
			"griffin": url_for("page_griffin"),
		},
		"navigation": [
			{"name": HtmlEntitySymbol.HOME.value, "href": url_for("page_index"), },
			{"name": HtmlEntitySymbol.STATE.value, "href": url_for("page_state", repository=RepositoryType.IN_MEMORY.value), },
			{"name": HtmlEntitySymbol.SCRAP.value, "href": url_for("page_scrap"), },
			{"name": "E", "href": url_for("page_throw_error"), },
		],
		"web_state": {
			"uptime": app_context.uptime,
		},
	}

	if app_context.config.app_debug:
		page_data.update({
			"network": {
				"hostname": socket.gethostname(),
				"socket.gethostbyname": socket.gethostbyname(socket.gethostname()),
				"socket.gethostbyname (local)": socket.gethostbyname(socket.gethostname() + ".local"),
			},
			"config": str(app_context.config),
		})

	for s in ViewSources:
		page_data["navigation"].append({"name": s.value, "href": url_for("page_view", view_source=s.value)})

	return page_data


@app.route("/")
def page_index():
	return render_template("home.html", page_data=get_page_data())


@app.route("/griffin/")
def page_griffin():
	return render_template("griffin.html", page_data=get_page_data())


@app.route("/state/")
@app.route("/state/<repository>/")
@app.route("/state/<repository>/<task_id>/")
def page_state(repository: str = RepositoryType.IN_MEMORY.value, task_id: int = None):
	app_context = get_app_context()
	page_data = get_page_data()
	try:
		match repository:
			case RepositoryType.IN_MEMORY.value: repo = app_context.repository_in_memory
			case RepositoryType.PERSISTENT.value: repo = app_context.repository_persistent
			case _: repo = app_context.repository_in_memory  # fallback

		page_data["state"] = {
			"uptime": app_context.uptime,
			"psutil": {
				"cpu_load": psutil.cpu_percent(0.1),
				"memory_percent": psutil.virtual_memory().percent,
				"disk_percent": psutil.disk_usage("/").percent,
			},
			"process": {
				"pid": os.getpid(),
			},
			"active_repository": repository,
			"active_task_id": task_id,
			"repositories": {
				repository_type.value: url_for("page_state", repository=repository_type.value) for repository_type in RepositoryType
			},
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
				"tasks": repo.read_recent_tasks_all(app_context.config.listing_limits.scraps),
				"task_detail_link_base": url_for("page_state", repository=repository),
			})

		return render_template("state.html", page_data=page_data)
	except Exception as ex:
		return render_exception_page(ex, page_data)


@app.route("/scrap/", methods=["GET", "POST"])
def page_scrap():
	app_context = get_app_context()
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

		match request.method, request.form.get("form", None):
			case ("POST", "scrap"):
				if request.form.get(f"source-{ViewSources.ROUMEN_KECY.value}", None) is not None:
					tasks.append(app_context.task_factory.create_task_roumen_kecy())
				if request.form.get(f"source-{ViewSources.ROUMEN_MASO.value}", None) is not None:
					tasks.append(app_context.task_factory.create_task_roumen_maso())

			case ("POST", "yt_dl"):
				if request.form.get("url-list", None) is not None:
					urls = tuple(url.strip() for url in request.form.get("url-list", "").split())
					tasks.append(app_context.task_factory.create_task_youtube_dl(urls))

			case ("POST", "ftp"):
				tasks.extend([app_context.task_factory.create_task_ftp_sync(task_type) for task_type in TaskType if task_type is not TaskType.DUMMY])

		for task in tasks:
			app_context.task_executor.submit(task)

	except Exception as ex:
		return render_exception_page(ex, page_data=page_data)

	return render_template("scrap.html", page_data=page_data)


@app.route("/view/<view_source>/")
def page_view(view_source: str):
	app_context = get_app_context()
	page_data = get_page_data({"view_source": view_source})
	try:
		match view_source:
			case ViewSources.ROUMEN_KECY.value: task_def = TaskClassAndType(TaskClass.SCRAP, TaskType.ROUMEN_KECY)
			case ViewSources.ROUMEN_MASO.value: task_def = TaskClassAndType(TaskClass.SCRAP, TaskType.ROUMEN_MASO)
			case _: raise ValueError(f"Invalid view type '{view_source}'.")

		items = app_context.repository_persistent.read_recent_task_items(
			task_def,
			app_context.config.listing_limits.images
		)

		page_data.update({
			"base_path": url_for("static", filename=app_context.config.scrappers.storage_path_for_static),
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


def init_app_context(flask_app: Flask) -> AppContext:
	ctx = AppContext.create(flask_app=flask_app, config_file=CONFIG_FILE)

	ctx.logger.info(f"App context created using config '{CONFIG_FILE}'.")
	ctx.logger.debug(f"{ctx.config=}")

	ctx.logger.info(f"Loading .env file...")
	menvloader.load_env_file(logger=ctx.logger)

	if ctx.config.server.port is None:
		raise ValueError(f"Server port not specified in '{CONFIG_FILE}'")

	flask_app.ctx = ctx
	return ctx


if __name__ == "__main__":
	ctx = init_app_context(app)

	app.run(
		host=ctx.config.server.host,
		port=ctx.config.server.port,
		debug=ctx.config.server.debug
	)
