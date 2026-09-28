"""Fail-closed errors. No nearest-match, no silent substitution."""


class FrozenUnavailable(LookupError):
    """Requested freeze identity or observation is not available."""


class VersionMismatch(FrozenUnavailable):
    """Requested version tuple does not match a published freeze."""


class ConsumptionForbidden(RuntimeError):
    """Refit, OOS evaluation, Kalshi join, residual, or quality-strip requested."""


class ProvenanceRequired(ValueError):
    """Consumer asked for a projection that would drop material quality fields."""
