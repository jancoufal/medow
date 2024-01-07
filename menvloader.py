from logging import Logger
import os


def load_env_file(file_name: str = ".env", logger: Logger = None):
	def _log(message: str):
		if logger is not None:
			logger.info(message)

	with open(file_name, "rt") as f:
		lines = [l.strip() for l in f.readlines() if not l.strip().startswith("#") and not len(l.strip()) == 0]
		env_tuples = tuple(l.split("=", 1) for l in lines)
		for var_name, var_value in env_tuples:
			if len(var_value) == 0:
				_log(f"Unsetting environment variable '{var_name}'")
				os.environ.pop(var_name)
			else:
				_log(f"Setting environment variable '{var_name}' to '{var_value}'")
				os.environ[var_name] = var_value
