import traceback
from typing import Optional

from .portfolio import get_buying_power, get_current_position_qty
from .market_data import get_latest_price
from alpaca.trading.enums import OrderSide
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import TimeInForce

def submit_market_order(trading_client: TradingClient, symbol: str, side: OrderSide, qty: float):

    if qty <= 0:
        return None

    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=side,
        time_in_force=TimeInForce.DAY,
    )
    return trading_client.submit_order(order_data=order)


def decide_and_trade(
    trading_client: TradingClient,
    data_client: StockHistoricalDataClient,
    symbol: str,
    signal: str,
) -> Optional[str]:
    """
    Execute trades based on current holdings and signal.
    Logic:
      - If not holding and signal == BUY => buy max affordable shares
      - If holding and signal == SELL => sell all
      - Otherwise => no action
    """
    signal = signal.upper()
    current_qty = get_current_position_qty(trading_client, symbol)

    if current_qty == 0 and signal == "BUY":
        try:
            max_qty = get_buying_power(trading_client) / get_latest_price(data_client, symbol)
            if max_qty <= 0:
                return f"Insufficient buying power to buy {symbol}: no action"
            submit_market_order(trading_client, symbol, OrderSide.BUY, max_qty)
            return f"BUY order submitted for {symbol} (qty={max_qty})"
        except Exception:
            return f"BUY failed for {symbol}: {traceback.format_exc()}"

    if current_qty > 0 and signal == "SELL":
        try:
            submit_market_order(trading_client, symbol, OrderSide.SELL, current_qty)
            return f"SELL order submitted for {symbol} (qty={current_qty})"
        except Exception:
            return f"SELL failed for {symbol}: {traceback.format_exc()}"

    # No action cases
    if current_qty == 0 and signal == "SELL":
        return f"No position and SELL signal for {symbol}: no action"
    if current_qty > 0 and signal == "BUY":
        return f"Already holding and BUY signal for {symbol}: no action"

    return None
