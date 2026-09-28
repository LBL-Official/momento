"""Jump ITI alias. Same module object as roller.superasi.iti.store."""

import sys

from roller.superasi.iti import store as _impl

sys.modules[__name__] = _impl
