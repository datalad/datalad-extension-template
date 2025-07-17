"""DataLad PublicnEUro extension"""

from datalad_next.url_operations import any

from datalad_publicneuro._version import __version__

__docformat__ = 'restructuredtext'

__all__ = []


# Add the publicneuro+http-handler to datalad-next's _url_handlers

handler_name = 'datalad_publicneuro.url_operations.publicneuro.PublicNeuroHttpUrlOperations'
any._url_handlers['publicneuro+http'] = (handler_name,)
any._url_handlers['publicneuro+https'] = (handler_name,)
