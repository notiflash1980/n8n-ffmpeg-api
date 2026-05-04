from flask import Flask, request, jsonify, send_file
import os
import requests
import subprocess
import threading
import sys # <-- IMPORTANTE: Para forzar la salida de logs

app = Flask(__name__)

# Función para imprimir inmediatamente en los logs de Render
def log_info(mensaje):
    print(f"🔄 {mensaje}", flush=True)

def generar_video_async(images, duration, audio_url):
    try:
        log_info("INICIANDO HILO DE VIDEO")
        
        # 1. Limpieza total antes de empezar
        for f in ["output.mp4", "list.txt", "audio.mp3"]:
            if os.path.exists(f): 
                os.remove(f)
                log_info(f"Archivo residual eliminado: {f}")

        local_images = []
        log_info(f"Vamos a descargar {len(images)} imagenes de Pollinations.")
        
        for i, item in enumerate(images): # <-- CORRECCIÓN AQUÍ: n8n manda un array de objetos, no solo URLs directas
            # Si 'item' es un diccionario, extraemos la URL. Si ya es un texto, lo usamos directo.
            url = item.get("url") if isinstance(item, dict) else item
            
            filename = f"img_{i}.jpg"
            log_info(f"Descargando {filename} desde {url[:50]}...")
            
            # Subimos el timeout a 30s porque Pollinations a veces es muy lento
            r = requests.get(url, timeout=30) 
            if r.status_code == 200:
                with open(filename, "wb") as f: 
                    f.write(r.content)
                local_images.append(filename)
                log_info(f"✅ {filename} descargada correctamente.")
            else:
                log_info(f"❌ Error al descargar {filename}: Código {r.status_code}")

        # 2. Audio
        has_audio = False
        if audio_url:
            log_info("Descargando audio...")
            r_audio = requests.get(audio_url, timeout=10)
            if r_audio.status_code == 200:
                with open("audio.mp3", "wb") as f: f.write(r_audio.content)
                has_audio = True
                log_info("✅ Audio descargado.")

        # 3. Crear list.txt
        log_info("Creando archivo list.txt...")
        with open("list.txt", "w") as f:
            for img in local_images:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration}\n")
            # En FFmpeg la última imagen debe repetirse sin duración para evitar cuelgues
            if local_images:
                f.write(f"file '{local_images[-1]}'\n")

        # 4. CONFIGURACIÓN DE EMERGENCIA (Bajo consumo de RAM)
        fps = 25
        # d es la duración en frames por cada imagen individual
        frames_por_imagen = duration * fps
        
        # Bajamos la escala de proceso a 320 para que Render no sufra
        video_filter = (
            f"scale=320:-1,zoompan=z='min(zoom+0.0015,1.25)':d={frames_por_imagen}:s=720x1280:fps={fps},"
            "format=yuv420p"
        )

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt"]
        if has_audio: cmd += ["-i", "audio.mp3"]

        cmd += [
            "-vf", video_filter,
            "-vcodec", "libx264",
            "-preset", "ultrafast",
            "-maxrate", "1M",      # <--- Limita el uso de CPU/Datos
            "-bufsize", "2M",      # <--- Limita el uso de RAM
            "-threads", "1",       # <--- Usa solo un núcleo
            "-pix_fmt", "yuv420p"
        ]

        if has_audio:
            cmd += ["-acodec", "aac", "-shortest"]
        
        cmd.append("output.mp4")

        log_info(f"Lanzando comando FFmpeg: {' '.join(cmd)}")

        # Ejecución
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ ERROR FFmpeg: {result.stderr}", flush=True)
        else:
            print("✅ VIDEO GENERADO EXITOSAMENTE", flush=True)

    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN EL HILO: {e}", flush=True)

@app.route("/render", methods=["POST"])
def render():
    print("🔔 Petición de Render recibida", flush=True)
    data = request.get_json()
    
    # IMPORTANTE: Si mandas un error desde n8n de golpe, veremos aquí qué llega realmente
    if not data:
        return jsonify({"status": "error", "message": "No se recibió JSON"}), 400

    images = data.get("images", [])
    duration = int(data.get("duration", 5)) # Aseguramos que sea entero
    audio_url = data.get("audio")

    # Lanzar en segundo plano
    thread = threading.Thread(target=generar_video_async, args=(images, duration, audio_url))
    thread.start()

    return jsonify({
        "status": "processing",
        "message": "Generando video. Revisa /video en unos minutos."
    }), 202 # <-- 202 Accepted es más correcto que 200

@app.route("/video", methods=["GET"])
def get_video():
    if os.path.exists("output.mp4"):
        return send_file("output.mp4", mimetype="video/mp4")
    return jsonify({"status": "error", "message": "Procesando o no encontrado"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
