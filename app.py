from flask import Flask, request, jsonify
from utils import format_ml_signal, send_telegram_message
from storage import save_signal

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "ml-forex server running"}), 200


@app.route("/predict", methods=["POST"])
def predict():
    """
    Espera un JSON desde TradingView con algo como:
    {
        "ticker": "EURUSD",
        "prediction": "BUY",
        "open_price": 1.0850,
        "sl": 1.0820,
        "tp": 1.0880,
        "timeframe": 15,
        "time": "2026-02-10 16:00:00"
    }
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "JSON inválido o vacío"}), 400

    try:
        ticker = str(data.get("ticker", "UNKNOWN"))
        model_prediction = str(data.get("prediction", "BUY")).upper()
        open_price = float(data.get("open_price"))
        sl = float(data.get("sl"))
        tp = float(data.get("tp"))
        timeframe = int(data.get("timeframe"))
        time_str = str(data.get("time"))

        msg = format_ml_signal(
            ticker=ticker,
            model_prediction=model_prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=timeframe,
            time_str=time_str,
        )

        ok, resp = send_telegram_message(msg)

        if not ok:
            return jsonify({"status": "error", "detail": resp}), 500

        return jsonify({"status": "ok", "message": "Signal sent to Telegram"}), 200

    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
