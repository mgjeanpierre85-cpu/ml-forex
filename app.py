from flask import Flask, request, jsonify
from utils import format_ml_signal, send_telegram_message
from storage import save_signal, save_signal_db, init_db
from datetime import datetime

app = Flask(__name__)

# Inicializa la base de datos al arrancar la app
init_db()

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "ml-forex server running"}), 200

@app.route("/predict", methods=["POST"])
def predict():
    # DEBUG: Imprimir lo que llega exactamente
    raw_body = request.data.decode('utf-8', errors='ignore').strip()
    content_type = request.headers.get('Content-Type')
    print("Raw body received:", raw_body)
    print("Content-Type received:", content_type)

    # Si llega solo "BUY" o "SELL" (texto plano de TradingView)
    if raw_body in ["BUY", "SELL"]:
        print("Body simple detectado: creando JSON manual")
        data = {
            "ticker": "BTCUSD",  # temporal, después lo sacamos de otro lado o de query si TV lo envía
            "prediction": raw_body,
            "open_price": 0.0,   # temporal
            "sl": 0.0,
            "tp": 0.0,
            "timeframe": 1,
            "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        # Si llega JSON real (como en Postman), parsearlo
        data = request.get_json(silent=True)
        if not data:
            print("Error: No se pudo parsear JSON (data is None)")
            return jsonify({"error": "JSON inválido o vacío"}), 400

    try:
        ticker = str(data.get("ticker", "UNKNOWN"))
        model_prediction = str(data.get("prediction", "BUY")).upper()
        open_price = float(data.get("open_price", 0.0))
        sl = float(data.get("sl", 0.0))
        tp = float(data.get("tp", 0.0))
        timeframe = int(data.get("timeframe", 1))
        time_str = str(data.get("time")) or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        msg = format_ml_signal(
            ticker=ticker,
            model_prediction=model_prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=timeframe,
            time_str=time_str,
        )

        save_signal(
            ticker=ticker,
            prediction=model_prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=timeframe,
            signal_time=time_str
        )

        save_signal_db(
            ticker=ticker,
            prediction=model_prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=timeframe,
            signal_time=time_str
        )

        ok, resp = send_telegram_message(msg)
        if not ok:
            print("Error al enviar a Telegram:", resp)
            return jsonify({"status": "error", "detail": resp}), 500

        return jsonify({"status": "ok", "message": "Signal sent to Telegram"}), 200

    except Exception as e:
        print("Exception in /predict:", str(e))
        return jsonify({"status": "error", "detail": str(e)}), 400

@app.route("/debug-csv", methods=["GET"])
def debug_csv():
    try:
        with open("signals.csv", "r", encoding="utf-8") as f:
            content = f.read()
        return f"<pre>{content}</pre>", 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
