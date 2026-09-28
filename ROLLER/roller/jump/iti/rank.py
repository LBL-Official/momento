"""Jump ITI alias. Same module object as roller.superasi.iti.rank."""

import sys

from roller.superasi.iti import rank as _impl

sys.modules[__name__] = _impl
