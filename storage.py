import csv
import os
from datetime import datetime

FILE_PATH = "signals.csv"

# Crear archivo con encabezados si no existe
if not os.path.exists(FILE_PATH):
    with open(FILE_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "ticker",
            "prediction",
            "open_price",
            "sl",
            "tp",
            "timeframe",
            "signal_time"
        ])

def save_signal(ticker, prediction, open_price, sl, tp, timeframe, signal_time):
    with open(FILE_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.utcnow().isoformat(),
            ticker,
            prediction,
            open_price,
            sl,
            tp,
            timeframe,
            signal_time
        ])
