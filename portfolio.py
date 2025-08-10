import traceback
from alpaca.trading.client import TradingClient

def get_current_position_qty(trading_client: TradingClient, symbol: str) -> float:
    """Return current position quantity for the given symbol (0 if none)."""
    try:
        position = trading_client.get_open_position(symbol)
        return float(position.qty)
    except Exception:
        print(traceback.format_exc())
        return 0.0


def get_buying_power(trading_client: TradingClient) -> float:
    account = trading_client.get_account()
    # Use non_marginable buying power
    bp = getattr(account, "non_marginable_buying_power", None)
    try:
        return float(bp)
    except Exception:
        print(traceback.format_exc())
        return 0.0


