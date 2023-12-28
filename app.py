import concurrent.futures
import logging
import os
import random
import sys
import traceback
from pathlib import Path

from flask import Flask, url_for, render_template, request

import mconfig
import scrappers
from mcontext import AppContext
from mstate import WebState
from mtasks import TaskScrapSource, TaskYoutubeDownload

CONFIG_FILE = "config.toml"
app = Flask(__name__)


GLOBAL_APP_CONTEXT: AppContext


def get_page_data(page_values: dict = None):
	HTML_ENTITY_SYMBOL_HOME = "&#x2302;"
	HTML_ENTITY_SYMBOL_STATE = "&#x225f;"  # "&#x22f1;"
	HTML_ENTITY_SYMBOL_STATS = "&#x03a3;"  # "&Sigma;"
	HTML_ENTITY_SYMBOL_RELOAD = "&#x21ca;"

	page_data = {
		"site": GLOBAL_APP_CONTEXT.config.site_title,
		"head": {
			"less": url_for("static", filename="site.less"),
		},
		"page_values": page_values,
		"current": {
			"endpoint": None if request.endpoint is None else url_for(request.endpoint, **page_values if page_values is not None else {}),
			"image_dir": url_for("static", filename=GLOBAL_APP_CONTEXT.config.storage.source_static),
			"debug": GLOBAL_APP_CONTEXT.config.debug,
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
			"uptime": GLOBAL_APP_CONTEXT.state.get_uptime(),
			"int_count": GLOBAL_APP_CONTEXT.state.get_int_count(),
		},
		"config": {
			"storage": str(GLOBAL_APP_CONTEXT.config.storage),
		},
	}

	for s in scrappers.Source:
		if s is not scrappers.Source.NOOP:
			page_data["navigation"].append({"name":s.value, "href":url_for("page_view", source=s.value)})

	return page_data


@app.route("/")
def page_index():
	return render_template("home.html", page_data=get_page_data())


@app.route("/griffin/")
def page_griffin():
	return render_template("griffin.html", page_data=get_page_data())


@app.route("/state/")
def page_state():
	page_data = get_page_data()
	state = GLOBAL_APP_CONTEXT.state
	page_data["state"] = {
		"uptime": state.get_uptime(),
		"task_results": state.get_task_results(),
	}

	return render_template("state.html", page_data=page_data)


@app.route("/stats/")
def page_stats():
	page_data = get_page_data()
	reader = scrappers.DbStatReader.create(GLOBAL_APP_CONTEXT.config.persistence.sqlite_datafile)
	page_data["stats"] = {
		"last_scraps": reader.read_last_scraps(GLOBAL_APP_CONTEXT.config.limits.scraps),
	}

	return render_template("stats.html", page_data=page_data)


@app.route("/scrap/", methods=["GET"])
def page_scrap():
	page_data = get_page_data()
	try:
		# debug
		page_data["request"] = {
			"method": request.method,
			"args": request.args,
			"form": request.form,
		}

		page_data["sources"] = [s for s in scrappers.Source if s is not scrappers.Source.NOOP]

		if request.method == "GET" and "auth-key" in request.args.keys():
			if GLOBAL_APP_CONTEXT.config.auth.key == request.args.get("auth-key"):

				for source in scrappers.Source:
					if request.args.get(f"source-{source.name}") is not None:
						GLOBAL_APP_CONTEXT.logger.debug(f"Enqueueing task for source '{source.name}'.")
						GLOBAL_APP_CONTEXT.task_executor.submit(TaskScrapSource(GLOBAL_APP_CONTEXT, source))

				if request.args.get("url-list") is not None:
					url_list = [url.strip() for url in request.args.get("url-list").split()]
					for url in url_list:
						GLOBAL_APP_CONTEXT.logger.debug(f"Enqueueing task for url '{url}'.")
						GLOBAL_APP_CONTEXT.task_executor.submit(TaskYoutubeDownload(GLOBAL_APP_CONTEXT, url))

				# page_data["scrapper_results"] = {s: scrap(s) for s in scrappers.Source if s is not scrappers.Source.NOOP}
			else:
				page_data["auth_error"] = {
					"title": "Authentication error",
					"message": random.choice(GLOBAL_APP_CONTEXT.config.auth.error_messages),
				}
	except:
		return render_exception_page(page_data=page_data)

	return render_template("scrap.html", page_data=page_data)


@app.route("/view/<source>/")
def page_view(source):
	page_data = get_page_data({"source": source})
	try:
		reader = scrappers.DbScrapReader.create(GLOBAL_APP_CONTEXT.config.persistence.sqlite_datafile, scrappers.Source.of(source))
		page_data["images"] = reader.read_recent_items(GLOBAL_APP_CONTEXT.config.limits.images)
		return render_template("view.html", page_data=page_data)
	except:
		return render_exception_page(page_data=page_data)


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


def render_exception_page(page_data:dict, exc_info=None):
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


def fake_scrap(scrapper_source: scrappers.Source):
	r = scrappers.result.Result(scrapper_source)

	for i in range(5):
		r.on_item(scrappers.result.ResultItem.createSucceeded(
			f"relative_path_{i}",
			f"remote_url_{i}"
			))

	for i in range(5):
		try:
			raise KeyError("test item exception")
		except:
			r.on_item(scrappers.result.ResultItem.createFailed(f"image_name_{i}"))

	if scrapper_source == scrappers.Source.ROUMEN_MASO:
		try:
			raise KeyError("test scrapper exception")
		except:
			r.on_scrapping_exception(scrappers.result.ExceptionInfo.createFromLastException())

	r.on_scrapping_finished()

	return r


def scrap(scrapper_source: scrappers.Source):
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


if __name__ == "__main__":

	ctx_config = mconfig.Config.from_file(CONFIG_FILE)

	logging.basicConfig(
		format=ctx_config.logging.format,
		level=ctx_config.logging.level,
	)

	ctx_logger = logging.getLogger(ctx_config.logging.name)
	ctx_logger.info(f"Config '{CONFIG_FILE}' loaded.")
	ctx_logger.debug(f"{ctx_config=}")

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
