import os
from flask import Flask, request, jsonify, send_file
from utils import format_ml_signal, send_telegram_message
from storage import (
    save_signal, 
    save_signal_db, 
    init_db, 
    FILE_PATH, 
    get_db_connection   # ← Agregado
)
from datetime import datetime

app = Flask(__name__)

# Inicializa la base de datos al arrancar la app
init_db()

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "ml-forex server running"}), 200

# ... (mantengo tu /predict igual, solo copio lo que ya tenías) ...
@app.route("/predict", methods=["POST"])
def predict():
    # (tu código actual de /predict se mantiene igual - lo omito aquí por brevedad, pero pégalo completo)
    # ... tu código de predict ...
    pass   # ← reemplaza esto con tu código completo de predict

# Ruta debug-csv (la que ya tenías)
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

# Ruta download-csv (con BOM para que Excel lo abra mejor)
@app.route("/download-csv", methods=["GET"])
def download_csv():
    try:
        if os.path.exists(FILE_PATH):
            today = datetime.utcnow().strftime("%Y%m%d")
            download_name = f"ml_forex_signals_{today}.csv"
            
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            
            # BOM para Excel en Latinoamérica
            bom_content = '\ufeff' + content
            from io import BytesIO
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

# Ruta para cerrar señal (mejorada y corregida)
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
        
        # Calcular WIN / LOSS
        if prediction == "BUY":
            result = "WIN" if close_price >= open_price else "LOSS"
        else:
            result = "WIN" if close_price <= open_price else "LOSS"
        
        pips = round((close_price - open_price) * 10000 if prediction == "BUY" else (open_price - close_price) * 10000, 1)
        
        # Actualizar
        cur.execute("""
            UPDATE ml_forex_signals 
            SET close_price = %s, result = %s, pips = %s 
            WHERE id = %s
        """, (close_price, result, pips, signal_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Mensaje de cierre
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
