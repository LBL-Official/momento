"""JumpQuery. Capability in → Systimo tunnel → source adapter → envelope."""

from roller.jump.data.router import capabilities, dispatch

run = dispatch
__all__ = ("capabilities", "dispatch", "run")
