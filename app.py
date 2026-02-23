import os
import json
from flask import Flask, request, jsonify, send_file
from utils import format_ml_signal, send_telegram_message
from storage import save_signal, save_signal_db, init_db, FILE_PATH, get_db_connection
from datetime import datetime
from io import BytesIO

app = Flask(__name__)

init_db()

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "ML-Forex Pro Server Running"}), 200

@app.route("/download-csv", methods=["GET"])
def download_csv():
    try:
        return send_file(FILE_PATH, as_attachment=True, mimetype='text/csv')
    except Exception as e:
        return jsonify({"error": f"Archivo no encontrado: {str(e)}"}), 404

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON inválido"}), 400
    
    try:
        prediction = str(data.get("prediction", "")).upper()
        ticker = str(data.get("ticker", "UNKNOWN")).upper()
        
        # SI LA PREDICCIÓN ES 'EXIT', REENVIAR A LA LÓGICA DE CIERRE
        if prediction == "EXIT":
            return process_close(data)

        # LÓGICA DE ENTRADA
        open_price = round(float(data.get("open_price", 0.0)), 5)
        sl = round(float(data.get("sl", 0.0)), 5)
        tp = round(float(data.get("tp", 0.0)), 5)
        
        # Identificador único (Sincronizado con PineScript)
        signal_id = data.get("signal_id", "N/A")
        tf_raw = data.get("timeframe", "UNKNOWN")
        tf_for_db = int(tf_raw) if str(tf_raw).isdigit() else 0
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Formatear y enviar a Telegram
        msg = format_ml_signal(
            ticker=ticker,
            model_prediction=prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=tf_raw,
            time_str=time_str
        )
        
        # Guardar (Añade el signal_id en el comentario o campo dedicado de tu storage)
        save_signal(ticker=ticker, prediction=prediction, open_price=open_price, sl=sl, tp=tp, timeframe=tf_for_db, signal_time=time_str)
        save_signal_db(ticker=ticker, prediction=prediction, open_price=open_price, sl=sl, tp=tp, timeframe=tf_for_db, signal_time=time_str)
        
        send_telegram_message(msg)
        return jsonify({"status": "ok", "signal_id": signal_id}), 200

    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 400

# Lógica compartida para cerrar señales
def process_close(data):
    try:
        ticker = str(data.get("ticker", "")).upper()
        close_price = round(float(data.get("close_price", 0.0)), 5)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Intentar buscar por ticker pendiente
        cur.execute("SELECT id, open_price, prediction FROM ml_forex_signals WHERE ticker = %s AND result = 'PENDING' ORDER BY timestamp DESC LIMIT 1", (ticker,))
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return jsonify({"error": "No pending signal"}), 404
        
        signal_id_db, open_price, prediction = row
        
        # CALCULO DE RESULTADO Y PIPS DINÁMICO
        result = "WIN" if (prediction == "BUY" and close_price >= open_price) or (prediction == "SELL" and close_price <= open_price) else "LOSS"
        
        # MULTIPLICADOR: 100 para JPY, 10000 para el resto
        multiplier = 100 if "JPY" in ticker else 10000
        pips = round((close_price - open_price if prediction == "BUY" else open_price - close_price) * multiplier, 1)
        
        cur.execute("UPDATE ml_forex_signals SET close_price = %s, result = %s, pips = %s WHERE id = %s", (close_price, result, pips, signal_id_db))
        conn.commit()
        cur.close()
        conn.close()
        
        msg = (f"🏁 <b>CIERRE {ticker}</b>\n"
               f"Resultado: {'🟢' if result == 'WIN' else '🔴'} {result}\n"
               f"Precio Cierre: {close_price:.5f}\n"
               f"Pips: {pips}")
        send_telegram_message(msg)
        return jsonify({"status": "ok", "pips": pips}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/close-signal", methods=["POST"])
def manual_close():
    return process_close(request.get_json(silent=True))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
