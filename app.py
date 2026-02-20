import os
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
        # 1. Extraer y limpiar: Forzamos la conversión a float y redondeamos a 5 decimales
        # Al usar data.get() con un valor por defecto claro, evitamos que use datos de la petición anterior
        ticker = str(data.get("ticker", "UNKNOWN")).upper()
        model_prediction = str(data.get("prediction", "BUY")).upper()
        
        # Redondeamos a 5 decimales para evitar números infinitos tipo 1.123000000001
        open_price = round(float(data.get("open_price", 0.0)), 5)
        sl = round(float(data.get("sl", 0.0)), 5)
        tp = round(float(data.get("tp", 0.0)), 5)
        
        timeframe = str(data.get("timeframe", "UNKNOWN"))
        
        # 2. Manejo de tiempo
        time_received = data.get("time")
        time_str = str(time_received) if time_received else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # 3. Formatear mensaje (Asegúrate que format_ml_signal no esté acumulando texto)
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

@app.route("/download-csv", methods=["GET"])
def download_csv():
    try:
        if os.path.exists(FILE_PATH):
            today = datetime.utcnow().strftime("%Y%m%d")
            download_name = f"ml_forex_signals_{today}.csv"
            
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            
            # BOM para Excel
            bom_content = '\ufeff' + content
            output = BytesIO(bom_content.encode('utf-8'))
            output.seek(0)
            
            return send_file(
                output,
                mimetype="text/csv",
                as_attachment=True,
                download_name=download_name
            )
        else:
            return jsonify({"error": "CSV file not found"}), 404
    except Exception as e:
        print(f"Error en /download-csv: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/close-signal", methods=["POST"])
def close_signal():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON inválido o vacío"}), 400
   
    try:
        ticker = str(data.get("ticker", "")).upper()
        close_price = float(data.get("close_price"))
        time_str = data.get("time") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, open_price, prediction 
            FROM ml_forex_signals 
            WHERE ticker = %s AND result = 'PENDING' 
            ORDER BY timestamp DESC LIMIT 1
        """, (ticker,))
        
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return jsonify({"error": f"No hay señal PENDING para {ticker}"}), 404
        
        signal_id, open_price, prediction = row
        
        if prediction == "BUY":
            result = "WIN" if close_price >= open_price else "LOSS"
        else:
            result = "WIN" if close_price <= open_price else "LOSS"
        
        pips = round((close_price - open_price) * 10000 if prediction == "BUY" else (open_price - close_price) * 10000, 1)
        
        cur.execute("""
            UPDATE ml_forex_signals 
            SET close_price = %s, result = %s, pips = %s 
            WHERE id = %s
        """, (close_price, result, pips, signal_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        msg = f"🏁 <b>CIERRE {ticker}</b>\nResultado: {result}\nPrecio Cierre: {close_price:.5f}\nPips: {pips}"
        send_telegram_message(msg)
        
        print(f"✅ Señal cerrada: {ticker} → {result} ({pips} pips)")
        return jsonify({"status": "ok", "result": result, "pips": pips}), 200
   
    except Exception as e:
        print(f"Error en /close-signal: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
