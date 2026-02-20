import csv
import os
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

FILE_PATH = "signals.csv"
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# CSV STORAGE (Actualizado)
# =========================
if not os.path.exists(FILE_PATH):
    with open(FILE_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow([
            "timestamp", "ticker", "prediction", "open_price", 
            "sl", "tp", "timeframe", "signal_time", 
            "close_price", "result", "pips"
        ])

def save_signal(ticker, prediction, open_price, sl, tp, timeframe, signal_time, close_price=None, result="PENDING", pips=None):
    with open(FILE_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow([
            datetime.utcnow().isoformat(),
            ticker,
            prediction,
            open_price,
            sl,
            tp,
            timeframe,
            signal_time,
            close_price,
            result,
            pips
        ])

# =========================
# POSTGRESQL STORAGE
# =========================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # TIP: Cambiamos timeframe a TEXT por si acaso, o lo dejamos INTEGER si confías en el filtro de app.py
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ml_forex_signals (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ticker TEXT NOT NULL,
            prediction TEXT NOT NULL,
            open_price NUMERIC,
            sl NUMERIC,
            tp NUMERIC,
            timeframe TEXT,  -- Cambiado a TEXT para evitar errores de tipo
            signal_time TEXT,
            close_price NUMERIC DEFAULT NULL,
            result TEXT DEFAULT 'PENDING',
            pips NUMERIC DEFAULT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def save_signal_db(ticker, prediction, open_price, sl, tp, timeframe, signal_time, close_price=None, result="PENDING", pips=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ml_forex_signals (
            timestamp, ticker, prediction, open_price, sl, tp, timeframe, signal_time,
            close_price, result, pips
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        datetime.utcnow(),
        ticker,
        prediction,
        open_price,
        sl,
        tp,
        str(timeframe), # Aseguramos que sea string para la DB
        signal_time,
        close_price,
        result,
        pips
    ))
    conn.commit()
    cur.close()
    conn.close()
