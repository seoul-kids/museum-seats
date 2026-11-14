"""Registry of museum scrapers. To add a museum, write a module with INFO + fetch() and list it here."""
from . import nfm_kids

ALL = [nfm_kids]
