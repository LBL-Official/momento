"""Jump ITI alias. Same module object as roller.superasi.iti.stress_question."""

import sys

from roller.superasi.iti import stress_question as _impl

sys.modules[__name__] = _impl
