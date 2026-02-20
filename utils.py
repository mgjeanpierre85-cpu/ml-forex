import requests
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"


def format_ml_signal(ticker, model_prediction, open_price, sl, tp, timeframe, time_str):
    direction = "BUY" if model_prediction == "BUY" else "SELL"

    # time_str esperado: "YYYY-MM-DD HH:MM:SS"
    dt_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    date_formatted = dt_obj.strftime("%m/%d/%Y")

    msg = (
        "🚨 <b>~ ML Signal ~</b>🤖\n\n"
        f"📊 <b>Pair:</b>           {ticker}\n"
        f"↕️ <b>Direction:</b>    {direction}\n"
        f"💵 <b>Entry:</b>          {open_price:.5f}\n"
        f"🛑 <b>SL:</b>              {sl:.5f}\n"
        f"✅ <b>TP:</b>              {tp:.5f}\n"
        f"⏰ <b>TF:</b>              {timeframe}m\n"
        f"📅 <b>Date:</b>          {date_formatted}"
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
