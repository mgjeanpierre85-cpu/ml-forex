import csv
import os
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

FILE_PATH = "signals.csv"
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# CSV STORAGE (SE MANTIENE)
# =========================

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


# =========================
# POSTGRESQL STORAGE
# =========================

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ml_forex_signals (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            ticker TEXT,
            prediction TEXT,
            open_price NUMERIC,
            sl NUMERIC,
            tp NUMERIC,
            timeframe INTEGER,
            signal_time TEXT
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def save_signal_db(ticker, prediction, open_price, sl, tp, timeframe, signal_time):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO ml_forex_signals (
            timestamp, ticker, prediction, open_price, sl, tp, timeframe, signal_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        datetime.utcnow(),
        ticker,
        prediction,
        open_price,
        sl,
        tp,
        timeframe,
        signal_time
    ))

    conn.commit()
    cur.close()
    conn.close()
