import concurrent.futures
import logging
import os
import sys
import traceback
import socket
from pathlib import Path

from flask import Flask, url_for, render_template, request

import mconfig
import scrappers
from msource import sources
from mscrapper import DbStatReader, DbScrapReader
from mcontext import AppContext
from mstate import WebState
from mtasks import TaskDummy

CONFIG_FILE = "config.toml"
app = Flask(__name__)


GLOBAL_APP_CONTEXT: AppContext


def get_page_data(ctx: AppContext, page_values: dict = None):
	HTML_ENTITY_SYMBOL_HOME = "&#x2302;"
	HTML_ENTITY_SYMBOL_STATE = "&#x22f1;"  # "&#x225f;"
	HTML_ENTITY_SYMBOL_STATS = "&#x03a3;"  # "&Sigma;"
	HTML_ENTITY_SYMBOL_RELOAD = "&#x21ca;"

	page_data = {
		"site": ctx.config.site_title,
		"head": {
			"less": url_for("static", filename="site.less"),
		},
		"page_values": page_values,
		"current": {
			"endpoint": None if request.endpoint is None else url_for(request.endpoint, **page_values if page_values is not None else {}),
			"image_dir": url_for("static", filename=ctx.config.storage.source_static),
			"debug": ctx.config.debug,
		},
		"links": {
			"griffin": url_for("page_griffin"),
		},
		"navigation": [
			{"name": HTML_ENTITY_SYMBOL_HOME, "href": url_for("page_index"), },
			{"name": HTML_ENTITY_SYMBOL_STATE, "href": url_for("page_state"), },
			{"name": HTML_ENTITY_SYMBOL_STATS, "href": url_for("page_stats"), },
			{"name": HTML_ENTITY_SYMBOL_RELOAD, "href": url_for("page_scrap"), },
		],
		"web_state": {
			"uptime": ctx.state.get_uptime(),
			"next_task_id": ctx.next_task_id,
		},
		"python": {
			"version": sys.version,
		},
		"network": {
			"hostname": socket.gethostname(),
			"socket.gethostbyname": socket.gethostbyname(socket.gethostname()),
			"socket.gethostbyname (local)": socket.gethostbyname(socket.gethostname() + ".local"),
		},
		"config": {
			"storage": str(ctx.config.storage),
		},
	}

	for s in sources.Source:
		if s is not sources.Source.NOOP:
			page_data["navigation"].append({"name": s.value, "href": url_for("page_view", source=s.value)})

	return page_data


@app.route("/")
def page_index():
	return render_template("home.html", page_data=get_page_data(GLOBAL_APP_CONTEXT))


@app.route("/griffin/")
def page_griffin():
	return render_template("griffin.html", page_data=get_page_data(GLOBAL_APP_CONTEXT))


@app.route("/state/")
def page_state():
	page_data = get_page_data(GLOBAL_APP_CONTEXT)
	state = GLOBAL_APP_CONTEXT.state
	page_data["state"] = {
		"uptime": state.get_uptime(),
		"tasks": state.get_task_states(),
	}

	return render_template("state.html", page_data=page_data)


@app.route("/stats/")
def page_stats():
	page_data = get_page_data(GLOBAL_APP_CONTEXT)
	reader = DbStatReader.create(GLOBAL_APP_CONTEXT.config.persistence.sqlite_datafile)
	page_data["stats"] = {
		"last_scraps": reader.read_last_scraps(GLOBAL_APP_CONTEXT.config.limits.scraps),
	}

	return render_template("stats.html", page_data=page_data)


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

		page_data["sources"] = [s for s in sources.Source if s is not sources.Source.NOOP]

		match request.method, request.form.get("form", None):
			case ("POST", "scrap"):
				for source in sources.Source:
					if request.form.get(f"source-{source.name}") is not None:
						GLOBAL_APP_CONTEXT.logger.debug(f"Enqueueing task for source '{source.name}'.")
						# GLOBAL_APP_CONTEXT.task_executor.submit(TaskScrapSource(GLOBAL_APP_CONTEXT, source))
						GLOBAL_APP_CONTEXT.task_executor.submit(TaskDummy(GLOBAL_APP_CONTEXT, "source", source.name))

			case ("POST", "yt_dl"):
				if request.form.get("url-list") is not None:
					for url in (url.strip() for url in request.form.get("url-list", "").split()):
						GLOBAL_APP_CONTEXT.logger.debug(f"Enqueueing task for url '{url}'.")
						# GLOBAL_APP_CONTEXT.task_executor.submit(TaskYoutubeDownload(GLOBAL_APP_CONTEXT, url))
						GLOBAL_APP_CONTEXT.task_executor.submit(TaskDummy(GLOBAL_APP_CONTEXT, "YT-DL", url))

			case ("POST", "nas"):
				GLOBAL_APP_CONTEXT.logger.debug(f"Enqueueing 'Wake-up NAS' task.")
				GLOBAL_APP_CONTEXT.task_executor.submit(TaskDummy(GLOBAL_APP_CONTEXT, "NAS", "Wake-up"))

		# page_data["scrapper_results"] = {s: scrap(s) for s in scrappers.Source if s is not scrappers.Source.NOOP}
	except:
		return render_exception_page(page_data=page_data)

	return render_template("scrap.html", page_data=page_data)


@app.route("/view/<source>/")
def page_view(source):
	page_data = get_page_data(GLOBAL_APP_CONTEXT, {"source": source})
	try:
		reader = DbScrapReader.create(GLOBAL_APP_CONTEXT.config.persistence.sqlite_datafile, sources.Source.of(source))
		page_data["images"] = reader.read_recent_items(GLOBAL_APP_CONTEXT.config.limits.images)
		return render_template("view.html", page_data=page_data)
	except:
		return render_exception_page(page_data=page_data)


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


def render_exception_page(page_data: dict, exc_info=None):
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


def fake_scrap(scrapper_source: sources.Source):
	r = scrappers.result.Result(scrapper_source)

	for i in range(5):
		r.on_item(scrappers.result.ResultItem.create_succeeded(
			f"relative_path_{i}",
			f"remote_url_{i}"
			))

	for i in range(5):
		try:
			raise KeyError("test item exception")
		except:
			r.on_item(scrappers.result.ResultItem.create_failed(f"image_name_{i}"))

	if scrapper_source == sources.Source.ROUMEN_MASO:
		try:
			raise KeyError("test scrapper exception")
		except:
			r.on_scrapping_exception(scrappers.result.ExceptionInfo.create_from_last_exception())

	r.on_scrapping_finished()

	return r


def scrap(scrapper_source: sources.Source):
	scrapper_settings = scrappers.Settings(
		local_base_path=Path.cwd(),
		local_relative_path=Path("static").joinpath("images"),
		sqlite_datafile=Path(GLOBAL_APP_CONTEXT.config.persistence.sqlite_datafile),
		)

	scrapper = scrappers.create(
		source=scrapper_source,
		settings=scrapper_settings
		)

	scrap_result = scrapper.scrap()
	return scrap_result


def load_env_file(file_name: str = None, logger: logging.Logger = None):
	if logger is None:
		logger = logging.getLogger("env_loader")

	with open(file_name if file_name is not None else ".env", "rt") as f:
		lines = [l.strip() for l in f.readlines() if not l.strip().startswith("#") and not len(l.strip()) == 0]
		env_tuples = tuple(l.split("=", 1) for l in lines)
		for var_name, var_value in env_tuples:
			if len(var_value) == 0:
				logger.info(f"Unsetting environment variable '{var_name}'")
				os.environ.pop(var_name)
			else:
				logger.info(f"Setting environment variable '{var_name}' to '{var_value}'")
				os.environ[var_name] = var_value


if __name__ == "__main__":

	ctx_config = mconfig.Config.from_file(CONFIG_FILE)

	logging.basicConfig(
		format=ctx_config.logging.format,
		level=ctx_config.logging.level,
	)

	ctx_logger = logging.getLogger(ctx_config.logging.name)
	ctx_logger.info(f"Config '{CONFIG_FILE}' loaded.")
	ctx_logger.debug(f"{ctx_config=}")

	ctx_logger.info(f"Loading .env file...")
	load_env_file(logger=ctx_logger)

	if ctx_config.server.port is None:
		raise ValueError(f"Server port not specified in '{CONFIG_FILE}'")

	ctx_logger.debug(f"{ctx_config.persistence=}")

	if ctx_config.debug:
		ctx_logger.debug(f"{ctx_config.debug=}")
		ctx_logger.debug(f"{Path(os.getcwd())=}")
		new_path = Path(os.getcwd()) / ctx_config.persistence.sqlite_datafile
		ctx_logger.debug(f"{new_path=}")
		ctx_config.persistence.sqlite_datafile = new_path

	ctx_logger.debug(f"{ctx_config.persistence=}")

	GLOBAL_APP_CONTEXT = AppContext(
		app,
		ctx_logger,
		ctx_config,
		WebState(),
		0,  # task_id start
		concurrent.futures.ThreadPoolExecutor(max_workers=ctx_config.worker_thread.max_workers)
	)

	app.run(
		host=ctx_config.server.host,
		port=ctx_config.server.port,
		debug=ctx_config.debug
	)
