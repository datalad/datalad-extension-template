"""DataLad PublicnEUro extension"""

from datalad_publicneuro._version import __version__

__docformat__ = 'restructuredtext'

__all__ = [
    '__version__',
]


# Add the publicneuro+http-handler to datalad-next's _url_handlers

from datalad_next.url_operations import any
any._url_handlers['publicneuro+http'] = ('datalad_publicneuro.url_operations.publicneuro.PublicNeuroHttpUrlOperations',)
