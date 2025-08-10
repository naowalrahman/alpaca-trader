import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient

# Ensure sibling modules (e.g., data_fetcher, indicators, models) are importable
CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from data_fetcher import DataFetcher
from indicators import TechnicalIndicators


def get_today_ohlv(data_client: StockHistoricalDataClient, symbol: str):
    """Try to fetch today's open, high, low via snapshot API. Returns tuple or None."""
    from alpaca.data.requests import StockSnapshotRequest

    req = StockSnapshotRequest(symbol_or_symbols=symbol)
    daily_bar = data_client.get_stock_snapshot(req).get(symbol).daily_bar

    return daily_bar.open, daily_bar.high, daily_bar.low, daily_bar.volume


def get_latest_price(data_client: StockHistoricalDataClient, symbol: str) -> float:
    from alpaca.data.requests import StockLatestTradeRequest

    latest_trade = data_client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
    return latest_trade.get(symbol).price


def fetch_data_with_estimated_last_point(
    symbol: str,
    data_client: StockHistoricalDataClient,
    lookback_days: int = 365,
) -> pd.DataFrame:
    """
    Fetch daily data for the symbol and estimate the last data point using current price
    if the current price is not available. Intended to run near market close when final 
    close is not yet available.
    """
    fetcher = DataFetcher()
    start_date_str = (datetime.now().date() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    data = fetcher.fetch_historical_data(
        symbol=symbol,
        start_date=start_date_str,
        end_date=end_date_str,
        interval="1d",
    )

    last_idx = data.index[-1]
    last_date = last_idx.normalize()
    today_date = pd.Timestamp(datetime.now().date())
    if last_date == today_date:
        return data

    ohlv = get_today_ohlv(data_client, symbol)
    current_price = get_latest_price(data_client, symbol)

    # Create a synthetic today's bar using snapshot OHLV + latest price
    open_price, high_price, low_price, volume = ohlv
    synthetic = {
        "Open": open_price,
        "High": high_price,
        "Low": low_price,
        "Close": current_price,
        "Volume": volume,
        "Dividends": 0.0 if "Dividends" in data.columns else np.nan,
        "Stock Splits": 0.0 if "Stock Splits" in data.columns else np.nan,
        "Symbol": symbol,
    }
    data = pd.concat([data, pd.DataFrame([synthetic], index=[today_date])])

    # Compute indicators
    return TechnicalIndicators.calculate_all_indicators(data)


