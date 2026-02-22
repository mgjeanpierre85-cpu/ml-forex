import os
import json
from flask import Flask, request, jsonify, send_file
from utils import format_ml_signal, send_telegram_message
from storage import save_signal, save_signal_db, init_db, FILE_PATH, get_db_connection
from datetime import datetime
from io import BytesIO

app = Flask(__name__)

# Inicializa la base de datos al arrancar la app
init_db()

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "ml-forex server running"}), 200

# --- NUEVA RUTA: DESCARGA DE EXCEL (CSV) ---
@app.route("/download-csv", methods=["GET"])
def download_csv():
    try:
        # Esto envía el archivo signals.csv a tu navegador
        return send_file(FILE_PATH, as_attachment=True, mimetype='text/csv')
    except Exception as e:
        return jsonify({"error": f"No se encontró el archivo: {str(e)}"}), 404

@app.route("/predict", methods=["POST"])
def predict():
    # 1. Obtener y parsear el cuerpo del JSON
    raw_body = request.data.decode('utf-8', errors='ignore').strip()
    data = request.get_json(silent=True)
    
    if not data and raw_body:
        try:
            data = json.loads(raw_body)
        except Exception as e:
            print(f"Error parseando JSON manualmente: {e}")
    
    if not data:
        return jsonify({"error": "JSON inválido o vacío"}), 400
    
    try:
        # 2. Extracción de datos con limpieza
        ticker = str(data.get("ticker", "UNKNOWN")).upper()
        model_prediction = str(data.get("prediction", "BUY")).upper()
        
        # Redondeo a 5 decimales para precisión en Forex
        open_price = round(float(data.get("open_price", 0.0)), 5)
        sl = round(float(data.get("sl", 0.0)), 5)
        tp = round(float(data.get("tp", 0.0)), 5)
        
        # --- FIX CRÍTICO: TIMEFRAME ---
        tf_raw = data.get("timeframe", "UNKNOWN")
        tf_for_db = int(tf_raw) if str(tf_raw).isdigit() else 0
        
        # Manejo de tiempo
        time_received = data.get("time")
        time_str = str(time_received) if time_received else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. Formatear mensaje para Telegram
        msg = format_ml_signal(
            ticker=ticker,
            model_prediction=model_prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=tf_raw,
            time_str=time_str,
        )
        
        # 4. Guardado en archivos locales y Base de Datos SQL
        save_signal(ticker=ticker, prediction=model_prediction, open_price=open_price, sl=sl, tp=tp, timeframe=tf_for_db, signal_time=time_str)
        save_signal_db(ticker=ticker, prediction=model_prediction, open_price=open_price, sl=sl, tp=tp, timeframe=tf_for_db, signal_time=time_str)
        
        # 5. Envío de notificación
        ok, resp = send_telegram_message(msg)
        if not ok:
            return jsonify({"status": "error", "detail": resp}), 500
        
        return jsonify({"status": "ok", "message": "Signal processed and sent"}), 200
    
    except Exception as e:
        print(f"Error en /predict: {str(e)}")
        return jsonify({"status": "error", "detail": str(e)}), 400

@app.route("/close-signal", methods=["POST"])
def close_signal():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON inválido"}), 400
    
    try:
        ticker = str(data.get("ticker", "")).upper()
        close_price = round(float(data.get("close_price", 0.0)), 5)
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT id, open_price, prediction FROM ml_forex_signals WHERE ticker = %s AND result = 'PENDING' ORDER BY timestamp DESC LIMIT 1", (ticker,))
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return jsonify({"error": f"No hay señal PENDING para {ticker}"}), 404
        
        signal_id, open_price, prediction = row
        result = "WIN" if (prediction == "BUY" and close_price >= open_price) or (prediction == "SELL" and close_price <= open_price) else "LOSS"
        pips = round((close_price - open_price) * 10000 if prediction == "BUY" else (open_price - close_price) * 10000, 1)
        
        cur.execute("UPDATE ml_forex_signals SET close_price = %s, result = %s, pips = %s WHERE id = %s", (close_price, result, pips, signal_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        msg = (
            f"🏁 <b>CIERRE {ticker}</b>\n"
            f"Resultado: {'🟢' if result == 'WIN' else '🔴'} {result}\n"
            f"Precio Cierre: {close_price:.5f}\n"
            f"Pips: {pips}"
        )
        send_telegram_message(msg)
        
        return jsonify({"status": "ok", "result": result, "pips": pips}), 200
    except Exception as e:
        print(f"Error en /close-signal: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
