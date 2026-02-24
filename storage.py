import csv
import os
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

FILE_PATH = "signals_forex.csv" 
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
    # Eliminamos RealDictCursor temporalmente para la función de cierre o aseguramos compatibilidad
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Intentar crear la tabla base
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
            signal_id TEXT,
            close_price NUMERIC(15,5) DEFAULT NULL,
            result TEXT DEFAULT 'PENDING',
            pips NUMERIC(10,1) DEFAULT NULL
        );
    """)
    conn.commit()

    # 2. MIGRACIÓN MANUAL: Forzar la columna signal_id si no existe
    try:
        cur.execute("ALTER TABLE ml_forex_signals ADD COLUMN IF NOT EXISTS signal_id TEXT;")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Nota: signal_id ya existía o no se pudo agregar: {e}")

    cur.close()
    conn.close()

def save_signal_db(ticker, prediction, open_price, sl, tp, timeframe, signal_time, signal_id="N/A"):
    try:
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
    except Exception as e:
        print(f"Error guardando en DB: {e}")
        if 'conn' in locals(): conn.rollback()
