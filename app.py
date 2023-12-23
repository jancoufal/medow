from flask import Flask
import yaml

config = {}
app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
	return 'Hello World!'


if __name__ == "__main__":
	with open("config.yaml") as f:
		config = yaml.load(f, Loader=yaml.Loader)

	if config["server"]["port"] is None:
		raise ValueError("Server port not specified in config.yaml")

	app.run(
		host=config["server"]["host"],
		port=config["server"]["port"],
		debug=config["server"]["debug"]
	)
