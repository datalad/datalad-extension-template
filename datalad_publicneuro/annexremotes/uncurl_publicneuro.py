"""Run uncurl from datalad_next with the Publicneuro HTTP URL handler

This wrapper imports `datalad_publicneuro.url_operations` to register the
Publicneuro HTTP URL handler with datalad_next's uncurl command.

This is required until URL handlers in datalad_next use some other entry point
mechanism that allows to register new URL handlers from extensions with `uncurl`.
"""

# The following import will register the Publicneuro URL handler with uncurl
from datalad_next.annexremotes import uncurl


def main():
    uncurl.main()
