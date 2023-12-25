import enum

class Source(enum.Enum):
	NOOP = "noop"
	ROUMEN = "roumen"
	ROUMEN_MASO = "roumen-maso"

	@staticmethod
	def of(source):
		for e in Source:
			if e.value == source:
				return e
		return Source.NOOP