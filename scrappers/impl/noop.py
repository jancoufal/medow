from msource.sources import Source
from ..result import Result
from ..settings import Settings


class Noop(object):
	def __init__(self, settings: Settings):
		pass

	def scrap(self):
		result = Result(Source.NOOP)
		result.on_scrapping_finished()
		return result
