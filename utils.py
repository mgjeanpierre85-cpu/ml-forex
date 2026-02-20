import requests
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def format_ml_signal(ticker, model_prediction, open_price, sl, tp, timeframe, time_str):
    direction = "BUY" if model_prediction == "BUY" else "SELL"

    # --- LÓGICA DE CONVERSIÓN DE TIMEFRAME (Igual que en Google Script) ---
    tf_str = str(timeframe)
    if tf_str == "60":
        tf_display = "1H"
    elif tf_str == "240":
        tf_display = "4H"
    elif tf_str in ["1D", "D"]:
        tf_display = "1 Day"
    else:
        # Si es un número (minutos), le ponemos la 'm'
        tf_display = f"{tf_str}m" if tf_str.isdigit() else tf_str

    # --- MANEJO SEGURO DE FECHA ---
    try:
        dt_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        date_formatted = dt_obj.strftime("%m/%d/%Y")
    except:
        date_formatted = time_str # Si falla, enviamos el texto tal cual

    # --- SELECCIÓN DINÁMICA DE DECIMALES ---
    # Si es Oro (XAU) usamos 2 o 3, si es Forex usamos 5
    prec = 2 if "XAU" in ticker.upper() else 5

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
