from dataclasses import dataclass


@dataclass
class Stock:

    symbol: str | None = None

    company_name: str | None = None

    currency: str | None = None

    current_price: float | None = None

    market_cap: int | None = None

    trailing_pe: float | None = None

    forward_pe: float | None = None

    trailing_eps: float | None = None

    return_on_equity: float | None = None

    sector: str | None = None

    industry: str | None = None
