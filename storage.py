import csv
import os
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

FILE_PATH = "signals_forex.csv" # Cambiado para diferenciar de Gold
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# CSV STORAGE
# =========================
def save_signal(ticker, prediction, open_price, sl, tp, timeframe, signal_time, signal_id="N/A", close_price=None, result="PENDING", pips=None):
    file_exists = os.path.exists(FILE_PATH)
    with open(FILE_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        if not file_exists:
            writer.writerow(["timestamp", "ticker", "prediction", "open_price", "sl", "tp", "timeframe", "signal_time", "signal_id", "close_price", "result", "pips"])
        
        writer.writerow([datetime.utcnow().isoformat(), ticker, prediction, open_price, sl, tp, timeframe, signal_time, signal_id, close_price, result, pips])

# =========================
# POSTGRESQL STORAGE
# =========================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Usamos NUMERIC(15,5) para asegurar 5 decimales exactos en Forex
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ml_forex_signals (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ticker TEXT NOT NULL,
            prediction TEXT NOT NULL,
            open_price NUMERIC(15,5),
            sl NUMERIC(15,5),
            tp NUMERIC(15,5),
            timeframe TEXT,
            signal_time TEXT,
            signal_id TEXT,  -- Añadido para rastreo exacto
            close_price NUMERIC(15,5) DEFAULT NULL,
            result TEXT DEFAULT 'PENDING',
            pips NUMERIC(10,1) DEFAULT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def save_signal_db(ticker, prediction, open_price, sl, tp, timeframe, signal_time, signal_id="N/A"):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ml_forex_signals (
            ticker, prediction, open_price, sl, tp, timeframe, signal_time, signal_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (ticker, prediction, open_price, sl, tp, str(timeframe), signal_time, str(signal_id)))
    conn.commit()
    cur.close()
    conn.close()
