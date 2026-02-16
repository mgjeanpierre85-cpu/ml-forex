import os
from flask import Flask, request, jsonify, send_file
from utils import format_ml_signal, send_telegram_message
from storage import save_signal, save_signal_db, init_db, FILE_PATH
from datetime import datetime

app = Flask(__name__)

# Inicializa la base de datos al arrancar la app
init_db()

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "ml-forex server running"}), 200

@app.route("/predict", methods=["POST"])
def predict():
    # DEBUG: Imprimir lo que llega exactamente para monitoreo en Render
    raw_body = request.data.decode('utf-8', errors='ignore').strip()
    content_type = request.headers.get('Content-Type')
   
    print(f"--- Nueva Petición Recibida ---")
    print(f"Raw body received: {raw_body}")
    print(f"Content-Type received: {content_type}")
   
    # Intentar parsear JSON independientemente del Content-Type enviado por TV
    data = request.get_json(silent=True)
   
    # Si get_json falla (a veces por Content-Type text/plain), forzamos parseo manual
    if not data and raw_body:
        import json
        try:
            data = json.loads(raw_body)
        except Exception as e:
            print(f"Error parseando JSON manualmente: {e}")
   
    if not data:
        print("Error: No se pudo parsear JSON (data is None o está vacío)")
        return jsonify({"error": "JSON inválido o vacío"}), 400
   
    try:
        # Extraer datos con valores por defecto
        ticker = str(data.get("ticker", "UNKNOWN"))
        model_prediction = str(data.get("prediction", "BUY")).upper()
        open_price = float(data.get("open_price", 0.0))
        sl = float(data.get("sl", 0.0))
        tp = float(data.get("tp", 0.0))
        timeframe = str(data.get("timeframe", "UNKNOWN"))
       
        # Manejo de tiempo: usar el del JSON o el actual del servidor
        time_received = data.get("time")
        time_str = str(time_received) if time_received else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
       
        # Formatear mensaje para Telegram
        msg = format_ml_signal(
            ticker=ticker,
            model_prediction=model_prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=timeframe,
            time_str=time_str,
        )
       
        # Guardar en CSV
        save_signal(
            ticker=ticker,
            prediction=model_prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=timeframe,
            signal_time=time_str
        )
       
        # Guardar en DB
        save_signal_db(
            ticker=ticker,
            prediction=model_prediction,
            open_price=open_price,
            sl=sl,
            tp=tp,
            timeframe=timeframe,
            signal_time=time_str
        )
       
        # Enviar a Telegram
        ok, resp = send_telegram_message(msg)
        if not ok:
            print(f"Error al enviar a Telegram: {resp}")
            return jsonify({"status": "error", "detail": resp}), 500
       
        print(f"Señal procesada con éxito: {ticker} {model_prediction}")
        return jsonify({"status": "ok", "message": "Signal processed and sent"}), 200
   
    except Exception as e:
        print(f"Exception in /predict: {str(e)}")
        return jsonify({"status": "error", "detail": str(e)}), 400

# Ruta para ver el contenido del CSV como texto (debug)
@app.route("/debug-csv", methods=["GET"])
def debug_csv():
    try:
        if os.path.exists(FILE_PATH):
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            return f"<pre>{content}</pre>", 200
        else:
            return "Archivo CSV no encontrado", 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Ruta para descargar el CSV como archivo adjunto
@app.route("/download-csv", methods=["GET"])
def download_csv():
    try:
        if os.path.exists(FILE_PATH):
            today = datetime.utcnow().strftime("%Y%m%d")
            download_name = f"ml_forex_signals_{today}.csv"
           
            return send_file(
                FILE_PATH,
                mimetype="text/csv",
                as_attachment=True,
                download_name=download_name
            )
        else:
            return jsonify({"error": "CSV file not found"}), 404
    except Exception as e:
        print(f"Error en /download-csv: {str(e)}")
        return jsonify({"error": str(e)}), 500

# NUEVA RUTA: Cerrar una señal pendiente y calcular WIN/LOSS
@app.route("/close-signal", methods=["POST"])
def close_signal():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON inválido o vacío"}), 400
   
    try:
        ticker = data.get("ticker")
        if not ticker:
            return jsonify({"error": "Falta el campo 'ticker'"}), 400
        
        close_price = float(data.get("close_price"))
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Conectar a DB
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Buscar la última señal PENDING para ese ticker
        cur.execute("""
            SELECT id, open_price, prediction, sl, tp 
            FROM ml_forex_signals 
            WHERE ticker = %s AND result = 'PENDING' 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (ticker,))
        
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return jsonify({"error": f"No hay señal PENDING para {ticker}"}), 404
        
        signal_id, open_price, prediction, sl, tp = row
        
        # Calcular resultado (WIN/LOSS) - lógica básica
        if prediction == "BUY":
            result = "WIN" if close_price >= open_price else "LOSS"
        else:  # SELL
            result = "WIN" if close_price <= open_price else "LOSS"
        
        # Calcular pips aproximados (para pares con 4-5 decimales, multiplica x10000)
        pips = (close_price - open_price) * 10000 if prediction == "BUY" else (open_price - close_price) * 10000
        
        # Actualizar la señal
        cur.execute("""
            UPDATE ml_forex_signals 
            SET close_price = %s, 
                result = %s, 
                pips = %s 
            WHERE id = %s
        """, (close_price, result, pips, signal_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Formatear y enviar mensaje de cierre a Telegram
        close_msg = (
            f"🏁 <b>CIERRE {ticker}</b>\n"
            f"Resultado: {result}\n"
            f"Precio Cierre: {close_price:.5f}\n"
            f"Pips: {pips:.1f}"
        )
        ok, resp = send_telegram_message(close_msg)
        if not ok:
            print(f"Error enviando cierre a Telegram: {resp}")
        
        print(f"Señal cerrada: {ticker} - {result} - Pips: {pips}")
        return jsonify({
            "status": "ok",
            "message": "Señal cerrada",
            "result": result,
            "pips": pips
        }), 200
   
    except Exception as e:
        print(f"Error en /close-signal: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
