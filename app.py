import os
import json
from flask import Flask, request, jsonify, send_file
from utils import format_ml_signal, send_telegram_message
from storage import save_signal, save_signal_db, init_db, FILE_PATH, get_db_connection
from datetime import datetime

app = Flask(__name__)

# Inicializa la base de datos con la nueva estructura de 5 decimales
init_db()

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "ML-Forex Data Collector Running"}), 200

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

        # LÓGICA DE ENTRADA (Recolección de datos limpios)
        open_price = float(data.get("open_price", 0.0))
        sl = float(data.get("sl", 0.0))
        tp = float(data.get("tp", 0.0))
        
        # Identificador único (Sincronizado con PineScript)
        signal_id = str(data.get("signal_id", "N/A"))
        tf_raw = str(data.get("timeframe", "UNKNOWN"))
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # 1. GUARDAR DATA (Sincronizado con el nuevo storage.py)
        # Pasamos el signal_id para que no falten argumentos
        save_signal(ticker, prediction, open_price, sl, tp, tf_raw, time_str, signal_id)
        save_signal_db(ticker, prediction, open_price, sl, tp, tf_raw, time_str, signal_id)
        
        # 2. ENVIAR A TELEGRAM DE PRUEBA (Sincronizado con utils.py)
        msg = format_ml_signal(ticker, prediction, open_price, sl, tp, tf_raw, time_str)
        send_telegram_message(msg)
        
        return jsonify({"status": "data_saved", "signal_id": signal_id}), 200

    except Exception as e:
        print(f"Error en /predict: {e}")
        return jsonify({"status": "error", "detail": str(e)}), 400

def process_close(data):
    try:
        ticker = str(data.get("ticker", "")).upper()
        close_price = float(data.get("close_price", 0.0))
        signal_id = str(data.get("signal_id", "N/A"))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Intentar buscar por signal_id primero para máxima precisión
        if signal_id != "N/A":
            cur.execute("SELECT id, open_price, prediction FROM ml_forex_signals WHERE ticker = %s AND signal_id = %s AND result = 'PENDING'", (ticker, signal_id))
        else:
            cur.execute("SELECT id, open_price, prediction FROM ml_forex_signals WHERE ticker = %s AND result = 'PENDING' ORDER BY timestamp DESC LIMIT 1", (ticker,))
        
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return jsonify({"error": f"No pending signal for {ticker}"}), 404
        
        id_db, open_price, prediction = row
        
        # CÁLCULO DE PIPS (Diferencia Forex vs JPY)
        multiplier = 100 if "JPY" in ticker else 10000
        diff = close_price - open_price if prediction == "BUY" else open_price - close_price
        pips = round(diff * multiplier, 1)
        result = "WIN" if pips >= 0 else "LOSS"
        
        # Actualizar DB con precisión
        cur.execute("UPDATE ml_forex_signals SET close_price = %s, result = %s, pips = %s WHERE id = %s", (close_price, result, pips, id_db))
        conn.commit()
        cur.close()
        conn.close()
        
        # Mensaje simplificado para el room de prueba
        msg = (f"🏁 <b>CIERRE {ticker}</b>\n"
               f"Resultado: {'🟢' if result == 'WIN' else '🔴'} {result}\n"
               f"Pips: {pips}\n"
               f"ID: {signal_id}")
        send_telegram_message(msg)
        
        return jsonify({"status": "closed", "pips": pips}), 200
    except Exception as e:
        print(f"Error en /close-signal: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/close-signal", methods=["POST"])
def manual_close():
    return process_close(request.get_json(silent=True))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
