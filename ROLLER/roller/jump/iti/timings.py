"""Jump ITI alias. Same module object as roller.superasi.iti.timings."""

import sys

from roller.superasi.iti import timings as _impl

sys.modules[__name__] = _impl
