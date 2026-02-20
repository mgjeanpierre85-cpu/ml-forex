import requests
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def format_ml_signal(ticker, model_prediction, open_price, sl, tp, timeframe, time_str):
    direction = "BUY" if model_prediction == "BUY" else "SELL"

    # --- 1. Conversión de Timeframe para el mensaje de Telegram ---
    tf_val = str(timeframe)
    if tf_val == "60":
        tf_display = "1H"
    elif tf_val == "240":
        tf_display = "4H"
    elif tf_val in ["1D", "D"]:
        tf_display = "1 Day"
    else:
        # Si es un número (minutos), le ponemos la 'm' (ej: 15m)
        tf_display = f"{tf_val}m" if tf_val.isdigit() else tf_val

    # --- 2. Manejo Seguro de Fecha (Evita error 500) ---
    try:
        # Intentamos formatear si viene en el formato estándar
        dt_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        date_formatted = dt_obj.strftime("%m/%d/%Y")
    except Exception:
        # Si falla el parseo, usamos el string tal cual viene para no romper el servidor
        date_formatted = time_str

    # --- 3. Precisión Dinámica ---
    # Si es Oro/Plata usamos 2 decimales, si es Forex usamos 5
    is_metal = any(metal in ticker.upper() for metal in ["XAU", "XAG", "GOLD", "SILVER"])
    prec = 2 if is_metal else 5

    msg = (
        "🚨 <b>~ ML Signal ~</b>🤖\n\n"
        f"📊 <b>Pair:</b>            {ticker}\n"
        f"↕️ <b>Direction:</b>     {direction}\n"
        f"💵 <b>Entry:</b>          {open_price:.{prec}f}\n"
        f"🛑 <b>SL:</b>               {sl:.{prec}f}\n"
        f"✅ <b>TP:</b>               {tp:.{prec}f}\n"
        f"⏰ <b>TF:</b>               {tf_display}\n"
        f"📅 <b>Date:</b>           {date_formatted}"
    )
    return msg

def send_telegram_message(text):
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, str(e)
