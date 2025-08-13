# Alpaca Trader

A light wrapper around Alpaca's trading and market data APIs that:

- Fetches recent daily data for a symbol (estimating today's bar near close)
- Loads an ML model checkpoint and produces a BUY/SELL signal
- Places market orders according to a simple position/decision policy

Used with ML strategies produced by MALET, my (currently) private ML trading platform.

### Prerequisites

- Python 3.9+
- Packages: `alpaca-py`, `pandas`, `numpy`, `python-dotenv`

Install quickly:

```bash
pip install alpaca-py pandas numpy python-dotenv
```

### Credentials

Set the following environment variables. Paper and live trading use separate keys.

- Paper: `ALPACA_PAPER_API_KEY_ID`, `ALPACA_PAPER_API_SECRET_KEY`
- Live: `ALPACA_LIVE_API_KEY_ID`, `ALPACA_LIVE_API_SECRET_KEY`

Example `.env` file:

```bash
ALPACA_PAPER_API_KEY_ID="your_key_id"
ALPACA_PAPER_API_SECRET_KEY="your_secret_key"
ALPACA_LIVE_API_KEY_ID="your_key_id"
ALPACA_LIVE_API_SECRET_KEY="your_secret_key"
```

### Quick start (Paper Trading)

Strongly recommended to start with paper trading. Omit `--paper` only if you intend to trade live.

```bash
python trader.py --symbol SPY --model /path/to/model.pkl --paper
```

Typical output (pretty-printed as a dict):

```python
{
    'symbol': 'SPY',
    'signal': 'BUY',
    'decision': 'BUY order submitted for SPY (qty=... )',
    'paper': True,
    'timestamp': '2025-01-01T15:55:00.123456'
}
```

### CLI

```bash
python trader.py --symbol SYMBOL --model /path/to/model.pkl [--paper]
```

- `--symbol` (required): Ticker, e.g., `SPY`
- `--model` (required): Path to trained model checkpoint (`.pkl`)
- `--paper` (flag): Use paper trading account. If omitted, runs against LIVE. Be careful.

### How it works

- Data: `market_data.fetch_data_with_estimated_last_point` loads ~1 year of daily data using repo-local `data_fetcher` and appends a synthetic "today" bar using Alpaca snapshot OHLV and latest trade price when the final close isn't available yet.
- Model: `model_utils.load_trainer` loads `models.TradingModelTrainer` and calls `trainer.predict(df)`. The last prediction is mapped to a signal: 1 → BUY, 0 → SELL.
- Execution: `strategy.decide_and_trade`:
  - If not holding and signal == BUY → submit market BUY for max affordable qty using non-marginable buying power
  - If holding and signal == SELL → submit market SELL for full position
  - Otherwise → no action

### Repo-local dependencies

This package relies on sibling modules in `backend/src`:

- `data_fetcher.py`, `indicators.py`
- `models/TradingModelTrainer.py`

The modules are made importable by temporarily adding `backend/src` to `sys.path` at runtime. No additional setup is needed when running the CLI from anywhere inside the repo.

### Safety notes

> [!IMPORTANT]
> Default mode is LIVE if you omit `--paper`. Always pass `--paper` unless you are intentionally trading with real funds.

> [!NOTE]
> Orders are MARKET and sized using available non-marginable buying power. Adjust logic in `strategy.py` if you need different sizing/risk controls.

### Troubleshooting

- Missing credentials error:
  - Ensure the correct env vars are set (paper vs live) before running.
- Import errors around `data_fetcher`, `indicators`, or `models.TradingModelTrainer`:
  - If you're running from within MALET, run inside the `alpaca-trader` directory. The code auto-adds `backend/src` to `sys.path`.
  - If you don't have access to MALET, you must modify `model_utils.py` to load your own model and generate signals.
- Permission/401 error from Alpaca:
  - Verify key/secret pair matches the selected mode (`--paper` vs live) and that the account has access.

### Scheduling (optional)

To run near market close each day (paper), use this cron job:

```cron
55 15 * * 1-5 /usr/bin/python /path/to/repo/backend/src/alpaca-trader/trader.py --symbol SPY --model /path/to/model.pkl --paper >> /var/log/alpaca_trader.log 2>&1
```

What this does:

- Schedule: `55 15 * * 1-5` runs at 15:55 (3:55 PM) Monday–Friday in the server's local timezone.
- Command: launches the trader for `SPY` using the provided model path, in paper mode (`--paper`). Adjust the symbol/model as needed.
- Logging: `>> /var/log/alpaca_trader.log 2>&1` appends both stdout and stderr to the log file.

> [!NOTE]
> If your server timezone is not EST, adjust the minute/hour to align with your desired market window. You can also set `TZ=America/New_York` at the top of your crontab to pin the timezone.

