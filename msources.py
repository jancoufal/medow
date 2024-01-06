from enum import Enum


class ScrapSource(Enum):
	NOOP = "noop"
	ROUMEN = "roumen"
	ROUMEN_MASO = "roumen-maso"

	@staticmethod
	def of(source):
		for e in ScrapSource:
			if e.value == source:
				return e
		return ScrapSource.NOOP
