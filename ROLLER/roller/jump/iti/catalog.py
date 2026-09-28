"""Jump ITI alias. Same module object as roller.superasi.iti.catalog."""

import sys

from roller.superasi.iti import catalog as _impl

sys.modules[__name__] = _impl
