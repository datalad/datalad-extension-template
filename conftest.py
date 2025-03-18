# We are not using datalad directly, because we are practically
# requiring whatever setup datalad_next prefers, because we employ
# its tooling
from datalad_next.conftest import setup_package

pytest_plugins = ('datalad_core.tests.fixtures', 'datalad_next.tests.fixtures')

__all__ = ['setup_package']
