from flask import Flask
import yaml
import os

config = {}
app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
	sqldata_file = config["persistence"]["sqlite_datafile"]

	return f"<pre>Hello, {config};\n{os.path.exists(sqldata_file)=}</pre>"


if __name__ == "__main__":
	with open("config.yaml") as f:
		config = yaml.load(f, Loader=yaml.Loader)

	if config["server"]["port"] is None:
		raise ValueError("Server port not specified in config.yaml")

	if config["server"]["debug"]:
		config["persistence"]["sqlite_datafile"] = os.getcwd() + config["persistence"]["sqlite_datafile"]

	app.run(
		host=config["server"]["host"],
		port=config["server"]["port"],
		debug=config["server"]["debug"]
	)
