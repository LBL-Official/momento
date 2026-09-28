"""Pluggable research fee models. Production KalshiFeeModel is UNRESOLVED."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

MAKER_COEF = 0.0175
TAKER_COEF = 0.07
STRESS_MULTIPLIER = 2.0


def ceil_e6(x: float) -> int:
    return int(math.ceil(x * 1_000_000.0 - 1e-12))


def quadratic_fee_e6(coef: float, contracts: int, price_cents: int) -> int:
    """Research estimate: ceil(coef * C * P * (1-P)) to $0.000001.

    Copied from the frozen audit formula. Not a production KalshiFeeModel.
    Series multiplier assumed 1. KXNBAGAME maker multiplier UNKNOWN.
    """
    if contracts <= 0:
        return 0
    p = price_cents / 100.0
    raw = coef * contracts * p * (1.0 - p)
    return ceil_e6(raw)


def e6_to_cents(e6: int) -> float:
    return e6 / 10_000.0  # $1e-6 → cents


@dataclass(frozen=True)
class FeeQuote:
    amount_e6: int | None
    amount_cents: float | None
    status: str
    model_id: str
    note: str


class FeeModelInterface(ABC):
    model_id: str
    status: str

    @abstractmethod
    def calculate_entry_fee(self, contracts: int, price_cents: int, maker: bool) -> FeeQuote:
        raise NotImplementedError

    @abstractmethod
    def calculate_exit_fee(self, contracts: int, price_cents: int, maker: bool) -> FeeQuote:
        raise NotImplementedError

    @abstractmethod
    def calculate_settlement_fee(self, contracts: int) -> FeeQuote:
        raise NotImplementedError

    def calculate_total_fee(
        self,
        contracts: int,
        entry_cents: int,
        exit_cents: int | None,
        entry_maker: bool,
        exit_maker: bool,
        settled: bool,
    ) -> FeeQuote:
        parts = [self.calculate_entry_fee(contracts, entry_cents, entry_maker)]
        if exit_cents is not None:
            parts.append(self.calculate_exit_fee(contracts, exit_cents, exit_maker))
        if settled:
            parts.append(self.calculate_settlement_fee(contracts))
        if any(q.status == "UNAVAILABLE" for q in parts):
            return FeeQuote(None, None, "UNAVAILABLE", self.model_id, "component UNAVAILABLE")
        total_e6 = sum(int(q.amount_e6 or 0) for q in parts)
        return FeeQuote(
            total_e6,
            e6_to_cents(total_e6),
            self.status,
            self.model_id,
            "sum of available components",
        )


class ZeroFeeModel(FeeModelInterface):
    model_id = "ZERO_FEE_MODEL"
    status = "SIMULATED"

    def _zero(self, note: str) -> FeeQuote:
        return FeeQuote(0, 0.0, self.status, self.model_id, note)

    def calculate_entry_fee(self, contracts: int, price_cents: int, maker: bool) -> FeeQuote:
        return self._zero("zero research placeholder")

    def calculate_exit_fee(self, contracts: int, price_cents: int, maker: bool) -> FeeQuote:
        return self._zero("zero research placeholder")

    def calculate_settlement_fee(self, contracts: int) -> FeeQuote:
        return self._zero("documented 0 for simple yes/no — still SIMULATED here")


class PublishedScheduleEstimate(FeeModelInterface):
    model_id = "PUBLISHED_SCHEDULE_ESTIMATE"
    status = "ESTIMATED"

    def __init__(self, maker_coef: float = MAKER_COEF, taker_coef: float = TAKER_COEF):
        self.maker_coef = maker_coef
        self.taker_coef = taker_coef

    def _quote(self, contracts: int, price_cents: int, maker: bool, note: str) -> FeeQuote:
        coef = self.maker_coef if maker else self.taker_coef
        e6 = quadratic_fee_e6(coef, contracts, price_cents)
        return FeeQuote(e6, e6_to_cents(e6), self.status, self.model_id, note)

    def calculate_entry_fee(self, contracts: int, price_cents: int, maker: bool) -> FeeQuote:
        return self._quote(
            contracts,
            price_cents,
            maker,
            f"quadratic {'maker' if maker else 'taker'} entry; M=1",
        )

    def calculate_exit_fee(self, contracts: int, price_cents: int, maker: bool) -> FeeQuote:
        return self._quote(
            contracts,
            price_cents,
            maker,
            f"quadratic {'maker' if maker else 'taker'} exit; M=1",
        )

    def calculate_settlement_fee(self, contracts: int) -> FeeQuote:
        return FeeQuote(0, 0.0, self.status, self.model_id, "documented 0 for simple yes/no")


class CustomStressModel(PublishedScheduleEstimate):
    model_id = "CUSTOM_STRESS_MODEL"
    status = "SIMULATED"

    def __init__(self, multiplier: float = STRESS_MULTIPLIER):
        super().__init__(
            maker_coef=MAKER_COEF * multiplier,
            taker_coef=TAKER_COEF * multiplier,
        )
        self.multiplier = multiplier

    def _quote(self, contracts: int, price_cents: int, maker: bool, note: str) -> FeeQuote:
        q = super()._quote(contracts, price_cents, maker, note)
        return FeeQuote(
            q.amount_e6,
            q.amount_cents,
            self.status,
            self.model_id,
            f"{self.multiplier:g}× published coefficients; {note}",
        )


class ObservedProductionModel(FeeModelInterface):
    model_id = "OBSERVED_PRODUCTION_MODEL"
    status = "UNAVAILABLE"

    def _none(self) -> FeeQuote:
        return FeeQuote(
            None,
            None,
            self.status,
            self.model_id,
            "unavailable until verified against actual Kalshi execution",
        )

    def calculate_entry_fee(self, contracts: int, price_cents: int, maker: bool) -> FeeQuote:
        return self._none()

    def calculate_exit_fee(self, contracts: int, price_cents: int, maker: bool) -> FeeQuote:
        return self._none()

    def calculate_settlement_fee(self, contracts: int) -> FeeQuote:
        return self._none()


MODELS = {
    "ZERO_FEE_MODEL": ZeroFeeModel,
    "PUBLISHED_SCHEDULE_ESTIMATE": PublishedScheduleEstimate,
    "CUSTOM_STRESS_MODEL": CustomStressModel,
    "OBSERVED_PRODUCTION_MODEL": ObservedProductionModel,
}


def get_model(model_id: str) -> FeeModelInterface:
    return MODELS[model_id]()
