import requests
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def format_ml_signal(ticker, model_prediction, open_price, sl, tp, timeframe, time_str):
    direction = "BUY 🟢" if model_prediction == "BUY" else "SELL 🔴"

    # --- 1. Conversión de Timeframe ---
    tf_val = str(timeframe)
    mapping = {"60": "1H", "240": "4H", "D": "1 Day", "1D": "1 Day"}
    tf_display = mapping.get(tf_val, f"{tf_val}m" if tf_val.isdigit() else tf_val)

    # --- 2. Manejo de Fecha ---
    try:
        dt_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        date_formatted = dt_obj.strftime("%d/%m/%Y %H:%M")
    except:
        date_formatted = time_str

    # --- 3. Precisión Dinámica (Oro/Plata 2, JPY 3, Forex 5) ---
    ticker_up = ticker.upper()
    is_metal = any(m in ticker_up for m in ["XAU", "XAG", "GOLD", "SILVER"])
    is_jpy = "JPY" in ticker_up
    
    prec = 2 if is_metal else (3 if is_jpy else 5)

    msg = (
        "🚨 <b>~ ML Forex Signal ~</b> 🤖\n\n"
        f"📊 <b>Pair:</b>            {ticker_up}\n"
        f"↕️ <b>Direction:</b>       {direction}\n"
        f"💵 <b>Entry:</b>           {open_price:.{prec}f}\n"
        f"🛑 <b>SL:</b>              {sl:.{prec}f}\n"
        f"✅ <b>TP:</b>              {tp:.{prec}f}\n"
        f"⏰ <b>TF:</b>              {tf_display}\n"
        f"📅 <b>Date:</b>            {date_formatted}"
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
        return True, r.json()
    except Exception as e:
        return False, str(e)
