from flask import Flask, request, jsonify, send_file
import os
import requests
import subprocess
import threading

app = Flask(__name__)

def generar_video_async(images, duration, audio_url):
    try:
        # 1. Limpieza total antes de empezar
        for f in ["output.mp4", "list.txt", "audio.mp3"]:
            if os.path.exists(f): os.remove(f)

        local_images = []
        for i, url in enumerate(images):
            filename = f"img_{i}.jpg"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(filename, "wb") as f: f.write(r.content)
                local_images.append(filename)

        # 2. Audio
        has_audio = False
        if audio_url:
            r_audio = requests.get(audio_url, timeout=10)
            if r_audio.status_code == 200:
                with open("audio.mp3", "wb") as f: f.write(r_audio.content)
                has_audio = True

        # 3. Crear list.txt
        with open("list.txt", "w") as f:
            for img in local_images:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration}\n")
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

        # Ejecución
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ ERROR FFmpeg: {result.stderr}")
        else:
            print("✅ VIDEO GENERADO EXITOSAMENTE")

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")

@app.route("/render", methods=["POST"])
def render():
    data = request.get_json()
    images = data.get("images", [])
    duration = data.get("duration", 5)
    audio_url = data.get("audio")

    # Lanzar en segundo plano
    thread = threading.Thread(target=generar_video_async, args=(images, duration, audio_url))
    thread.start()

    return jsonify({
        "status": "processing",
        "message": "Generando video de 30s. Revisa /video en unos minutos."
    })

@app.route("/video", methods=["GET"])
def get_video():
    if os.path.exists("output.mp4"):
        return send_file("output.mp4", mimetype="video/mp4")
    return jsonify({"status": "error", "message": "Procesando o no encontrado"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
