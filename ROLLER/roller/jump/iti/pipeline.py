"""Jump ITI alias. Same module object as roller.superasi.iti.pipeline."""

import sys

from roller.superasi.iti import pipeline as _impl

sys.modules[__name__] = _impl
