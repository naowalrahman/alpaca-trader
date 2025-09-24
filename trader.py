import argparse
from datetime import datetime
from dotenv import load_dotenv

from .clients import get_alpaca_clients
from .market_data import fetch_data_with_estimated_last_point
from .model_utils import load_trainer, generate_signal
from .strategy import decide_and_trade
from pprint import pprint


def trade_with_model(
    trade_symbol: str,
    predict_symbol: str,
    model_path: str,
    paper: bool = True,
) -> dict:
    """
    End-to-end flow: fetch data (with estimated last point), load model, predict, and trade.
    Returns a structured result with decision details.
    """
    trading_client, data_client = get_alpaca_clients(paper=paper)

    df = fetch_data_with_estimated_last_point(predict_symbol)
    trainer = load_trainer(model_path)
    signal = generate_signal(trainer, df)
    decision = decide_and_trade(trading_client, trade_symbol, signal)

    return {
        "trade_symbol": trade_symbol,
        "predict_symbol": predict_symbol,
        "signal": signal,
        "decision": decision or "no_action",
        "paper": paper,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    load_dotenv()    

    parser = argparse.ArgumentParser(description="Alpaca trading runner with ML model prediction")
    parser.add_argument("--trade-symbol", required=True, help="Ticker symbol to trade i.e. submit orders with, e.g., SPUS")
    parser.add_argument("--predict-symbol", required=True, help="Ticker symbol to predict i.e. fetch data for, e.g., SPY")
    parser.add_argument("--model", required=True, help="Path to trained model checkpoint (.pkl)")
    parser.add_argument("--paper", action="store_true", help="Use paper trading account")
    args = parser.parse_args()

    result = trade_with_model(
        trade_symbol=args.trade_symbol,
        predict_symbol=args.predict_symbol,
        model_path=args.model,
        paper=args.paper,
    )

    pprint(result)


if __name__ == "__main__":
    main()


