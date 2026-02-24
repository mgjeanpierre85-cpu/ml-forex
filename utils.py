import requests
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def format_ml_signal(ticker, model_prediction, open_price, sl, tp, timeframe, time_str):
    # Aseguramos que la dirección sea texto limpio
    direction = "BUY 🟢" if str(model_prediction).upper() == "BUY" else "SELL 🔴"

    # --- 1. Conversión de Timeframe ---
    tf_val = str(timeframe)
    mapping = {"60": "1H", "240": "4H", "D": "1 Day", "1D": "1 Day"}
    tf_display = mapping.get(tf_val, f"{tf_val}m" if tf_val.isdigit() else tf_val)

    # --- 2. Manejo de Fecha ---
    try:
        # Intentar parsear si viene como string de sistema
        dt_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        date_formatted = dt_obj.strftime("%d/%m/%Y %H:%M")
    except:
        date_formatted = time_str

    # --- 3. Precisión de Forex (JPY 3, Otros 5) ---
    ticker_up = str(ticker).upper()
    is_jpy = "JPY" in ticker_up
    prec = 3 if is_jpy else 5

    # Blindaje contra valores no numéricos para evitar errores de formateo
    try:
        f_open = float(open_price)
        f_sl = float(sl)
        f_tp = float(tp)
    except:
        # Si falla la conversión, enviamos como texto para no tumbar el servidor
        return f"🚨 Error en formato de precios para {ticker_up}"

    msg = (
        "🚨 <b>~ ML Forex Signal ~</b> 🤖\n\n"
        f"📊 <b>Pair:</b>            {ticker_up}\n"
        f"↕️ <b>Direction:</b>       {direction}\n"
        f"💵 <b>Entry:</b>           {f_open:.{prec}f}\n"
        f"🛑 <b>SL:</b>              {f_sl:.{prec}f}\n"
        f"✅ <b>TP:</b>              {f_tp:.{prec}f}\n"
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
        print(f"Error enviando Telegram: {e}")
        return False, str(e)
