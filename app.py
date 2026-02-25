import os
import json
from flask import Flask, request, jsonify, send_file
from utils import format_ml_signal, send_telegram_message
from storage import save_signal, save_signal_db, init_db, FILE_PATH, get_db_connection
from datetime import datetime

app = Flask(__name__)

# Inicializa la base de datos y aplica migraciones (como agregar signal_id)
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

# ==============================================================================
# RUTA TEMPORAL PARA LIMPIAR SEÑALES VIEJAS (SOLO EJECUTAR UNA VEZ)
# ==============================================================================
@app.route("/reset-db-now", methods=["GET"])
def reset_db():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Marca todas las señales PENDING antiguas como OUTDATED
        cur.execute("UPDATE ml_forex_signals SET result = 'OUTDATED' WHERE result = 'PENDING';")
        conn.commit()
        cur.close()
        conn.close()
        return "✅ Base de datos de Forex limpiada: Señales viejas marcadas como OUTDATED.", 200
    except Exception as e:
        if conn:
            conn.close()
        return f"❌ Error al limpiar: {str(e)}", 500

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON inválido"}), 400
    
    try:
        prediction = str(data.get("prediction", "")).upper()
        ticker = str(data.get("ticker", "UNKNOWN")).upper()
        
        # Si la señal es un cierre (EXIT), saltamos a process_close
        if prediction == "EXIT":
            return process_close(data)

        # Conversión segura a float para la entrada
        open_price = float(data.get("open_price", 0.0))
        sl = float(data.get("sl", 0.0))
        tp = float(data.get("tp", 0.0))
        
        signal_id = str(data.get("signal_id", "N/A"))
        tf_raw = str(data.get("timeframe", "UNKNOWN"))
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Guardar en CSV y Base de Datos
        save_signal(ticker, prediction, open_price, sl, tp, tf_raw, time_str, signal_id)
        save_signal_db(ticker, prediction, open_price, sl, tp, tf_raw, time_str, signal_id)
        
        # 2. Notificar por Telegram (Canal de Laboratorio/Pruebas)
        msg = format_ml_signal(ticker, prediction, open_price, sl, tp, tf_raw, time_str)
        send_telegram_message(msg)
        
        return jsonify({"status": "data_saved", "signal_id": signal_id}), 200

    except Exception as e:
        print(f"Error en /predict: {e}")
        return jsonify({"status": "error", "detail": str(e)}), 400

def process_close(data):
    """
    Procesa el cierre de operaciones. 
    Busca por signal_id para asegurar que cerramos la operación correcta.
    """
    conn = None
    try:
        ticker = str(data.get("ticker", "")).upper()
        close_price = float(data.get("close_price", 0.0))
        signal_id = str(data.get("signal_id", "N/A"))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Buscar la señal PENDING
        if signal_id != "N/A":
            cur.execute("SELECT id, open_price, prediction FROM ml_forex_signals WHERE ticker = %s AND signal_id = %s AND result = 'PENDING' LIMIT 1", (ticker, signal_id))
        else:
            cur.execute("SELECT id, open_price, prediction FROM ml_forex_signals WHERE ticker = %s AND result = 'PENDING' ORDER BY timestamp DESC LIMIT 1", (ticker,))
        
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return jsonify({"error": f"No hay señal pendiente para {ticker} con ID {signal_id}"}), 404
        
        # Extraemos por posición (Cursor normal)
        id_db = row[0]
        open_price = float(row[1]) 
        prediction = str(row[2]).upper()
        
        # 2. Lógica de Pips / Puntos (Solo Forex y JPY para este servidor)
        if "JPY" in ticker:
            multiplier = 100
        else:
            multiplier = 10000
            
        diff = close_price - open_price if prediction == "BUY" else open_price - close_price
        pips = round(diff * multiplier, 1)
        result = "WIN" if pips >= 0 else "LOSS"
        
        # 3. Actualizar la base de datos
        cur.execute("""
            UPDATE ml_forex_signals 
            SET close_price = %s, result = %s, pips = %s 
            WHERE id = %s
        """, (close_price, result, pips, id_db))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # 4. Telegram
        emoji = '🟢' if result == 'WIN' else '🔴'
        msg = (f"🏁 <b>CIERRE {ticker}</b>\n"
               f"Resultado: {emoji} {result}\n"
               f"Pips/Puntos: {pips}\n"
               f"ID: {signal_id}")
        send_telegram_message(msg)
        
        return jsonify({"status": "closed", "pips": pips, "result": result}), 200

    except Exception as e:
        print(f"Error crítico en process_close: {e}")
        if conn:
            conn.close()
        return jsonify({"status": "error", "detail": str(e)}), 500

@app.route("/close-signal", methods=["POST"])
def manual_close():
    data = request.get_json(silent=True)
    return process_close(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
