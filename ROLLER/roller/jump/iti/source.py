"""Jump ITI alias. Same module object as roller.superasi.iti.source."""

import sys

from roller.superasi.iti import source as _impl

sys.modules[__name__] = _impl
