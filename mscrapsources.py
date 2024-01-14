from enum import Enum


# TODO: remove

class ScrapSource(Enum):
	ROUMEN = "roumen"
	ROUMEN_MASO = "roumen-maso"

	@staticmethod
	def of(source):
		for e in ScrapSource:
			if e.value == source:
				return e
		raise ValueError(f"Unknown source: {source}")
