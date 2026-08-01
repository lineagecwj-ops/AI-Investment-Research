from dataclasses import dataclass


@dataclass
class Stock:

    symbol: str

    company_name: str

    price: float

    currency: str