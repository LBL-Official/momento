"""Jump ITI alias. Same module object as roller.superasi.iti.versions."""

import sys

from roller.superasi.iti import versions as _impl

sys.modules[__name__] = _impl
