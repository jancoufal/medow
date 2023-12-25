from ..sources import Source
from ..settings import Settings
from ..result import Result

class Noop(object):
	def __init__(self, settings: Settings):
		pass

	def scrap(self):
		result = Result(Source.NOOP)
		result.on_scrapping_finished()
		return result
