import os
import pickle
import sys
from typing import Optional

import pandas as pd

# Ensure sibling modules (e.g., data_fetcher, indicators, models) are importable
CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from models.TradingModelTrainer import TradingModelTrainer


def load_trainer(model_path: str) -> TradingModelTrainer:
    with open(model_path, "rb") as f:
        models_object = pickle.load(f)
        return models_object["trainer"]


def generate_signal(trainer: TradingModelTrainer, df: pd.DataFrame) -> str:
    """
    Use the trained model to predict; last prediction 1 => BUY, 0 => SELL.
    """
    preds = trainer.predict(df)
    if len(preds) == 0:
        raise ValueError("Insufficient data for prediction")
    return "BUY" if int(preds[-1]) == 1 else "SELL"


