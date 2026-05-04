from flask import Flask, request, jsonify, send_file
import os
import requests
import subprocess
import threading
import sys
import time

app = Flask(__name__)

# Función para que los logs aparezcan al instante en Render
def log_info(mensaje):
    print(f"🔄 {mensaje}", flush=True)

def generar_video_async(images, duration, audio_url):
    try:
        log_info("--- INICIANDO PROCESO DE COCINADO ---")
        
        # 1. Limpieza de archivos de sesiones anteriores
        archivos_a_limpiar = ["output.mp4", "list.txt", "audio.mp3"]
        for i in range(10): # Limpiar posibles imágenes img_0...img_9
            archivos_a_limpiar.append(f"img_{i}.jpg")
            
        for f in archivos_a_limpiar:
            if os.path.exists(f): 
                try:
                    os.remove(f)
                except:
                    pass

        local_images = []
        log_info(f"Petición para procesar {len(images)} imágenes.")

        # 2. Descarga de imágenes con sistema de reintentos (Antiflemas)
        for i, item in enumerate(images):
            # Extraemos la URL (n8n suele mandar [{'url': '...'}, ...])
            url = item.get("url") if isinstance(item, dict) else item
            filename = f"img_{i}.jpg"
            
            descargada = False
            intentos_max = 3
            
            for intento in range(intentos_max):
                try:
                    log_info(f"Descargando {filename} (Intento {intento+1}/{intentos_max})...")
                    # Timeout de 60s para darle tiempo a la IA de Pollinations
                    r = requests.get(url, timeout=60)
                    
                    if r.status_code == 200:
                        with open(filename, "wb") as f:
                            f.write(r.content)
                        local_images.append(filename)
                        log_info(f"✅ {filename} lista.")
                        descargada = True
                        break
                    else:
                        log_info(f"⚠️ Pollinations respondió con error {r.status_code}. Reintentando...")
                except Exception as e:
                    log_info(f"⏳ Error o Timeout en {filename}. Reintentando en 2 segundos...")
                    time.sleep(2)
            
            if not descargada:
                log_info(f"❌ Saltando {filename} tras agotar reintentos.")

        if not local_images:
            log_info("❌ CRÍTICO: No se pudo descargar ninguna imagen. Abortando.")
            return

        # 3. Descarga de Audio (si existe)
        has_audio = False
        if audio_url:
            try:
                log_info(f"Descargando audio desde: {audio_url[:50]}...")
                r_audio = requests.get(audio_url, timeout=30)
                if r_audio.status_code == 200:
                    with open("audio.mp3", "wb") as f:
                        f.write(r_audio.content)
                    has_audio = True
                    log_info("✅ Audio preparado.")
            except:
                log_info("⚠️ No se pudo obtener el audio, se generará el video mudo.")

        # 4. Creación del archivo de lista para FFmpeg
        log_info("Generando list.txt...")
        with open("list.txt", "w") as f:
            for img in local_images:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration}\n")
            # Truco de FFmpeg: repetir la última imagen
            f.write(f"file '{local_images[-1]}'\n")

        # 5. Configuración de FFmpeg (Modo Ahorro de Energía para Render)
        fps = 25
        frames_por_imagen = int(duration) * fps
        
        # Filtro: Escala baja (320px) para no saturar la RAM y efecto Zoom suave
        video_filter = (
            f"scale=320:-1,zoompan=z='min(zoom+0.0015,1.25)':d={frames_por_imagen}:s=720x1280:fps={fps},"
            "format=yuv420p"
        )

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt"]
        if has_audio:
            cmd += ["-i", "audio.mp3"]

        cmd += [
            "-vf", video_filter,
            "-vcodec", "libx264",
            "-preset", "ultrafast", # El más rápido para consumir menos CPU
            "-maxrate", "1M",
            "-bufsize", "2M",
            "-threads", "1",        # Usar solo 1 núcleo para no ser baneado por Render
            "-pix_fmt", "yuv420p"
        ]

        if has_audio:
            cmd += ["-acodec", "aac", "-shortest"]
        
        cmd.append("output.mp4")

        log_info("🚀 Lanzando FFmpeg...")
        
        # Ejecutamos y capturamos salida
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        
        if resultado.returncode == 0:
            log_info("🏆 ¡VIDEO GENERADO CON ÉXITO!")
        else:
            log_info(f"❌ ERROR EN FFMPEG: {resultado.stderr}")

    except Exception as e:
        log_info(f"💥 ERROR CRÍTICO EN EL HILO: {str(e)}")

@app.route("/render", methods=["POST"])
def render():
    log_info("🔔 Petición /render recibida.")
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No JSON data received"}), 400

    images = data.get("images", [])
    duration = data.get("duration", 3)
    audio = data.get("audio")

    # Disparamos el hilo para que n8n no tenga que esperar
    hilo = threading.Thread(target=generar_video_async, args=(images, duration, audio))
    hilo.start()

    return jsonify({
        "status": "processing",
        "message": "Cocinando el video. Revisa /video en unos minutos."
    }), 202

@app.route("/video", methods=["GET"])
def get_video():
    if os.path.exists("output.mp4"):
        return send_file("output.mp4", mimetype="video/mp4")
    return jsonify({"status": "error", "message": "Video no listo o fallido"}), 404

# Ruta de bienvenida para el cron-job (que no de error 404)
@app.route("/", methods=["GET"])
def home():
    return "Servidor de Video Activo 🎥", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
  
