from .sources import Source
from .settings import Settings
from .impl import Noop, Roumen, RoumenMaso


def create(source:Source, settings:Settings):
	scrapper_classes = {
		Source.NOOP: Noop,
		Source.ROUMEN: Roumen,
		Source.ROUMEN_MASO: RoumenMaso,
	}

	scrapper_class = scrapper_classes.get(source, Noop)
	return scrapper_class(settings)
