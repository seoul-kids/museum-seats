"""Registry of museum scrapers. To add a museum, write a module with INFO + fetch() and list it here."""
from . import avi_kids, ksm_kids, nfm_kids, nmk_kids, swr

ALL = [nfm_kids, nmk_kids, ksm_kids, avi_kids, swr]
