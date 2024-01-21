import logging
import os
import socket
import sys
import traceback
from pathlib import Path
from enum import Enum
from http import HTTPStatus

from flask import Flask, url_for, render_template, request, redirect

from mcontext import AppRepositoryType, AppContext
from mscrappers_api import ScrapperType
import menvloader

CONFIG_FILE = "config.yaml"
app = Flask(__name__)


GLOBAL_APP_CONTEXT: AppContext


class HtmlEntitySymbol(Enum):
	HOME = "&#x2302;"
	STATE = "&#x22f1;"  # "&#x225f;"
	# STATS = "&#x03a3;"  # "&Sigma;"
	SCRAP = "&#x21ca;"


def get_page_data(ctx: AppContext, page_values: dict = None):
	page_data = {
		"site": ctx.config.site_title,
		"head": {
			"less": url_for("static", filename="site.less"),
		},
		"page_values": page_values,
		"current": {
			"endpoint": None if request.endpoint is None else url_for(request.endpoint, **page_values if page_values is not None else {}),
			"image_dir": url_for("static", filename=ctx.config.scrappers.storage_path_for_static),
			"debug": ctx.config.app_debug,
		},
		"links": {
			"griffin": url_for("page_griffin"),
		},
		"navigation": [
			{"name": HtmlEntitySymbol.HOME.value, "href": url_for("page_index"), },
			{"name": HtmlEntitySymbol.STATE.value, "href": url_for("page_state", repository=AppRepositoryType.IN_MEMORY.value), },
			# {"name": HtmlEntitySymbol.STATS.value, "href": url_for("page_stats"), },
			{"name": HtmlEntitySymbol.SCRAP.value, "href": url_for("page_scrap"), },
		],
		"web_state": {
			"uptime": ctx.uptime,
			"python_version": sys.version,
		},
		"network": {
			"hostname": socket.gethostname(),
			"socket.gethostbyname": socket.gethostbyname(socket.gethostname()),
			"socket.gethostbyname (local)": socket.gethostbyname(socket.gethostname() + ".local"),
		},
		"config": str(ctx.config),
	}

	for s in [ScrapperType.ROUMEN_KECY, ScrapperType.ROUMEN_MASO]:
		page_data["navigation"].append({"name": s.value, "href": url_for("page_view", source=s.value)})

	return page_data


@app.route("/")
def page_index():
	return render_template("home.html", page_data=get_page_data(GLOBAL_APP_CONTEXT))


@app.route("/griffin/")
def page_griffin():
	return render_template("griffin.html", page_data=get_page_data(GLOBAL_APP_CONTEXT))


@app.route("/state/")
@app.route("/state/<repository>/")
@app.route("/state/<repository>/<task_id>/")
def page_state(repository: str = AppRepositoryType.IN_MEMORY.value, task_id: int = None):
	match repository:
		case AppRepositoryType.IN_MEMORY.value: repo = GLOBAL_APP_CONTEXT.repository_in_memory
		case AppRepositoryType.PERSISTENT.value: repo = GLOBAL_APP_CONTEXT.repository_persistent
		case _: repo = GLOBAL_APP_CONTEXT.repository_in_memory  # fallback

	page_data = get_page_data(GLOBAL_APP_CONTEXT)
	page_data["state"] = {
		"uptime": GLOBAL_APP_CONTEXT.uptime,
		"active_repository": repository,
		"active_task_id": task_id,
		"repositories": {
			repository_type.value: url_for("page_state", repository=repository_type.value) for repository_type in AppRepositoryType
		},
	}

	if task_id is not None:
		task = repo.load_entity_scrap_task(task_id)
		page_data["state"].update({
			"page_view_mode": "task_detail",
			"task": task,
			"task_items": repo.read_scrap_task_items(task),
		})
	else:
		page_data["state"].update({
			"page_view_mode": "task_overview",
			"tasks": repo.read_recent_scrap_tasks_all(GLOBAL_APP_CONTEXT.config.listing_limits.scraps),
			"task_detail_link_base": url_for("page_state", repository=repository),
		})

	return render_template("state.html", page_data=page_data)


@app.route("/scrap/", methods=["GET", "POST"])
def page_scrap():
	page_data = get_page_data(GLOBAL_APP_CONTEXT)
	try:
		# debug
		page_data["request"] = {
			"method": request.method,
			"args": request.args,
			"form": request.form,
		}

		page_data["sources"] = [ScrapperType.ROUMEN_KECY, ScrapperType.ROUMEN_MASO]
		tasks = []

		match request.method, request.form.get("form", None):
			case ("POST", "scrap"):
				if request.form.get(f"source-{ScrapperType.ROUMEN_KECY.value}", None) is not None:
					tasks.append(GLOBAL_APP_CONTEXT.task_factory.create_task_roumen_kecy())
				if request.form.get(f"source-{ScrapperType.ROUMEN_MASO.value}", None) is not None:
					tasks.append(GLOBAL_APP_CONTEXT.task_factory.create_task_roumen_maso())

			case ("POST", "yt_dl"):
				if request.form.get("url-list", None) is not None:
					urls = tuple(url.strip() for url in request.form.get("url-list", "").split())
					tasks.append(GLOBAL_APP_CONTEXT.task_factory.create_task_youtube_dl(urls))

			case ("POST", "ftp"):
				GLOBAL_APP_CONTEXT.logger.debug(f"Enqueueing 'Sync to FTP/NAS' task.")
				# GLOBAL_APP_CONTEXT.task_executor.submit(TaskDummy(GLOBAL_APP_CONTEXT, "NAS", "Wake-up"))

		# page_data["scrapper_results"] = {s: scrap(s) for s in scrappers.Source if s is not scrappers.Source.NOOP}
	except Exception as ex:
		return render_exception_page(ex, page_data=page_data)

	return render_template("scrap.html", page_data=page_data)


@app.route("/view/<source>/")
def page_view(source):
	page_data = get_page_data(GLOBAL_APP_CONTEXT, {"source": source})
	try:
		items = GLOBAL_APP_CONTEXT.repository_persistent.read_recent_scrap_task_items(
			ScrapperType.of(source),
			GLOBAL_APP_CONTEXT.config.listing_limits.images
		)

		page_data.update({
			"base_path": url_for("static", filename=GLOBAL_APP_CONTEXT.config.scrappers.storage_path_for_static),
			"task_items": [item for item in items if item.local_path is not None]
		})

		return render_template("view.html", page_data=page_data)
	except Exception as ex:
		return render_exception_page(ex, page_data=page_data)


@app.errorhandler(404)
def page_not_found(e):
	page_data = get_page_data(GLOBAL_APP_CONTEXT)
	page_data["error"] = {
		"code": e.code,
		"name": e.name,
		"description": e.description,
	}
	# note that we set the 404 status explicitly
	return render_template('error.html', page_data=page_data), 404


def render_exception_page(ex: Exception, page_data: dict, exc_info=None):
	e = exc_info if exc_info is not None else sys.exc_info()
	exception_info = {
		"exception": {
			"endpoint": page_data["current"]["endpoint"],
			"type": e[0],
			"value": e[1],
			"traceback": traceback.format_tb(e[2]),
		}
	}
	return render_template("exception.html", page_data={**page_data, **exception_info})


if __name__ == "__main__":
	ctx = AppContext.create(flask_app=app, config_file=CONFIG_FILE)

	ctx.logger.info(f"App context created using config '{CONFIG_FILE}'.")
	ctx.logger.debug(f"{ctx.config=}")

	ctx.logger.info(f"Loading .env file...")
	menvloader.load_env_file(logger=ctx.logger)

	if ctx.config.server.port is None:
		raise ValueError(f"Server port not specified in '{CONFIG_FILE}'")

	GLOBAL_APP_CONTEXT = ctx

	app.run(
		host=ctx.config.server.host,
		port=ctx.config.server.port,
		debug=ctx.config.server.debug
	)
