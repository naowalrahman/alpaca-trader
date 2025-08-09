import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

import numpy as np
import pandas as pd

# Ensure sibling modules (e.g., data_fetcher, indicators, models) are importable
CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from data_fetcher import DataFetcher  # noqa: E402
from indicators import TechnicalIndicators  # noqa: E402
from models.TradingModelTrainer import TradingModelTrainer  # noqa: E402


def _get_env_flag(name: str, default: bool = True) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y"}


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


def get_current_position_qty(trading_client, symbol: str) -> int:
    """Return current position quantity for the given symbol (0 if none)."""
    try:
        position = trading_client.get_open_position(symbol)
        return int(float(position.qty))
    except Exception:
        # No position
        return 0


def get_buying_power(trading_client) -> float:
    account = trading_client.get_account()
    # Use non_marginable_buying_power to be conservative
    bp = getattr(account, "non_marginable_buying_power", None) or getattr(account, "buying_power", "0")
    try:
        return float(bp)
    except Exception:
        return 0.0


def submit_market_order(trading_client, symbol: str, side: str, qty: int):
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    if qty <= 0:
        return None

    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    return trading_client.submit_order(order_data=order)


def fetch_data_with_estimated_last_point(
    symbol: str,
    data_client,
    lookback_days: int = 365,
) -> pd.DataFrame:
    """
    Fetch daily data for the symbol and estimate the last data point using current price
    (intended to run near market close when final close is not yet available).
    """
    fetcher = DataFetcher()
    start_date_str = (datetime.now(timezone.utc).date() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = fetcher.fetch_historical_data(
        symbol=symbol,
        start_date=start_date_str,
        end_date=end_date_str,
        interval="1d",
    )

    # Get latest trade price from Alpaca data using documented SDK API
    try:
        from alpaca.data.requests import StockLatestTradeRequest

        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        latest_trades = data_client.get_stock_latest_trade(req)
        # Per docs, responses are keyed by symbol even for single symbol
        current_price = float(latest_trades[symbol].price)
    except Exception:
        # Fallback to last known close if Alpaca data fails
        current_price = float(data["Close"].iloc[-1]) if not data.empty else np.nan

    if data.empty:
        raise ValueError(f"No historical data for {symbol}")

    # If we already have today's row, override its Close with current price; otherwise append a new row
    last_idx = data.index[-1]
    today_date = pd.Timestamp(datetime.now(timezone.utc).date())

    if last_idx.normalize() == today_date:
        # Override the current day's close to the current price
        data = data.copy()
        data.loc[last_idx, "Close"] = current_price
        # Optionally adjust High/Low bounds to include current price
        data.loc[last_idx, "High"] = max(data.loc[last_idx, "High"], current_price)
        data.loc[last_idx, "Low"] = min(data.loc[last_idx, "Low"], current_price)
    else:
        # Create a synthetic today's bar using prior close and current price
        prev_close = float(data["Close"].iloc[-1])
        synthetic = {
            "Open": prev_close,
            "High": max(prev_close, current_price),
            "Low": min(prev_close, current_price),
            "Close": current_price,
            "Volume": 0,
            "Dividends": 0.0 if "Dividends" in data.columns else np.nan,
            "Stock Splits": 0.0 if "Stock Splits" in data.columns else np.nan,
            "Symbol": symbol,
        }
        data = pd.concat([data, pd.DataFrame([synthetic], index=[today_date])])

    # Compute indicators
    data_with_indicators = TechnicalIndicators.calculate_all_indicators(data)
    return data_with_indicators


def load_trainer(model_path: str) -> TradingModelTrainer:
    trainer = TradingModelTrainer()
    trainer.load_model(model_path)
    return trainer


def generate_signal(trainer: TradingModelTrainer, df: pd.DataFrame) -> str:
    """
    Use the trained model to predict; last prediction 1 => BUY, 0 => SELL.
    """
    preds = trainer.predict(df)
    if len(preds) == 0:
        raise ValueError("Insufficient data for prediction")
    return "BUY" if int(preds[-1]) == 1 else "SELL"


def decide_and_trade(
    trading_client,
    symbol: str,
    signal: str,
    default_qty: int = 1,
) -> Optional[str]:
    """
    Execute trades based on current holdings and signal.
    Logic:
      - If not holding and signal == BUY => buy
      - If holding and signal == SELL => sell all
      - Otherwise => no action
    """
    signal = signal.upper()
    current_qty = get_current_position_qty(trading_client, symbol)

    if current_qty == 0 and signal == "BUY":
        # Size by default quantity; ensure buying power allows at least 1 share
        try:
            submit_market_order(trading_client, symbol, "buy", max(1, int(default_qty)))
            return f"BUY order submitted for {symbol} (qty={max(1, int(default_qty))})"
        except Exception as e:
            return f"BUY failed for {symbol}: {e}"

    if current_qty > 0 and signal == "SELL":
        try:
            submit_market_order(trading_client, symbol, "sell", current_qty)
            return f"SELL order submitted for {symbol} (qty={current_qty})"
        except Exception as e:
            return f"SELL failed for {symbol}: {e}"

    # No action cases
    if current_qty == 0 and signal == "SELL":
        return f"No position and SELL signal for {symbol}: no action"
    if current_qty > 0 and signal == "BUY":
        return f"Already holding and BUY signal for {symbol}: no action"

    return None


def trade_with_model(
    symbol: str,
    model_path: str,
    paper: bool = None,
    default_qty: int = 1,
) -> dict:
    """
    End-to-end flow: fetch data (with estimated last point), load model, predict, and trade.
    Returns a structured result with decision details.
    """
    if paper is None:
        paper = _get_env_flag("ALPACA_USE_PAPER", True)

    trading_client, data_client = get_alpaca_clients(paper=paper)

    df = fetch_data_with_estimated_last_point(symbol, data_client=data_client)
    trainer = load_trainer(model_path)
    signal = generate_signal(trainer, df)
    decision = decide_and_trade(trading_client, symbol, signal, default_qty=default_qty)

    return {
        "symbol": symbol,
        "signal": signal,
        "decision": decision or "no_action",
        "paper": paper,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Alpaca trading runner with ML model prediction")
    parser.add_argument("--symbol", required=True, help="Ticker symbol, e.g., AAPL")
    parser.add_argument("--model", required=True, help="Path to trained model checkpoint (.pt) saved by TradingModelTrainer")
    parser.add_argument("--paper", default=None, choices=["true", "false", "1", "0"], help="Use paper trading account (default from env ALPACA_USE_PAPER=true)")
    parser.add_argument("--qty", type=int, default=1, help="Default order quantity when buying")
    args = parser.parse_args()

    paper_flag = None
    if args.paper is not None:
        paper_flag = args.paper.strip().lower() in {"true", "1", "yes", "y"}

    result = trade_with_model(
        symbol=args.symbol,
        model_path=args.model,
        paper=paper_flag,
        default_qty=args.qty,
    )
    # Print concise result
    print(result)


if __name__ == "__main__":
    main()


