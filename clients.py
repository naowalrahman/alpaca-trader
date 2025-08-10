import os
from typing import Tuple


def _get_alpaca_credentials(paper: bool) -> Tuple[str, str]:
    """Pick credentials for paper vs live, with compatible fallbacks."""
    if paper:
        api_key = os.getenv("ALPACA_PAPER_API_KEY_ID")
        secret_key = os.getenv("ALPACA_PAPER_API_SECRET_KEY")
    else:
        api_key = os.getenv("ALPACA_LIVE_API_KEY_ID")
        secret_key = os.getenv("ALPACA_LIVE_API_SECRET_KEY")

    if not api_key or not secret_key:
        raise RuntimeError(
            "Missing Alpaca credentials. Set paper or live keys: "
            "ALPACA_PAPER_API_KEY_ID/ALPACA_PAPER_API_SECRET_KEY or "
            "ALPACA_LIVE_API_KEY_ID/ALPACA_LIVE_API_SECRET_KEY."
        )

    return api_key, secret_key


def get_alpaca_clients(paper: bool = True):
    """
    Initialize Alpaca trading and data clients with separate keys for paper vs live.
    Uses envs (checked in order):
      - Paper: ALPACA_PAPER_API_KEY_ID, ALPACA_PAPER_API_SECRET_KEY
      - Live:  ALPACA_LIVE_API_KEY_ID,  ALPACA_LIVE_API_SECRET_KEY
    """
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.trading.client import TradingClient

    api_key, secret_key = _get_alpaca_credentials(paper)

    trading_client = TradingClient(api_key, secret_key, paper=paper)
    data_client = StockHistoricalDataClient(api_key, secret_key)
    return trading_client, data_client


