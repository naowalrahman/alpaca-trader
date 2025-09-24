import traceback
from typing import Optional, Literal

from .portfolio import get_buying_power, get_current_position_qty, get_current_position_value
from alpaca.trading.enums import OrderSide
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import TimeInForce

def submit_market_order(trading_client: TradingClient, symbol: str, side: OrderSide, method: Literal["notional", "qty"], amount: float):

    if amount <= 0:
        return None
    
    if method == "qty":
        order = MarketOrderRequest(
            symbol=symbol,
            qty=amount,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
    else:
        order = MarketOrderRequest(
            symbol=symbol,
            notional=amount,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
    return trading_client.submit_order(order_data=order)


def decide_and_trade(
    trading_client: TradingClient,
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
    print(f"Decide and trade for {symbol} with signal {signal}")
    current_position_value = get_current_position_value(trading_client, symbol)

    if current_position_value < 1 and signal == "BUY":
        try:
            notional = get_buying_power(trading_client)
            print(f"Notional: {notional}")
            if notional <= 0:
                return f"Insufficient buying power to buy {symbol}: no action"
            submit_market_order(trading_client, symbol, OrderSide.BUY, "notional", notional)
            return f"BUY order submitted for {symbol} (notional=${notional})"
        except Exception:
            return f"BUY failed for {symbol}: {traceback.format_exc()}"

    if current_position_value > 0 and signal == "SELL":
        try:
            current_position_qty = get_current_position_qty(trading_client, symbol)
            submit_market_order(trading_client, symbol, OrderSide.SELL, "qty", current_position_qty)
            return f"SELL order submitted for {symbol} (notional=${current_position_value})"
        except Exception:
            return f"SELL failed for {symbol}: {traceback.format_exc()}"

    # No action cases
    if current_position_value == 0 and signal == "SELL":
        return f"No position and SELL signal for {symbol}: no action"
    if current_position_value > 0 and signal == "BUY":
        return f"Already holding and BUY signal for {symbol}: no action"

    return None
