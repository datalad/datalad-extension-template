"""DataLad PublicnEUro extension"""

from datalad_next.url_operations import any

__docformat__ = 'restructuredtext'

__all__ = []


# Add the publicneuro+http-handler to datalad-next's _url_handlers

handler_name = 'datalad_publicneuro.url_operations.publicneuro.PublicNeuroHttpUrlOperations'
any._url_handlers['publicneuro\\+https'] = (handler_name,)  # noqa: SLF001
