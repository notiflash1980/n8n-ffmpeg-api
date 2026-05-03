from flask import Flask, request, jsonify, send_file
import os
import requests
import subprocess
import threading # 🧵 Necesario para trabajar en segundo plano

app = Flask(__name__)

# Función que hace el trabajo pesado fuera de la ruta principal
def generar_video_async(images, duration, audio_url):
    try:
        local_images = []
        # 1. Descarga
        for i, url in enumerate(images):
            filename = f"img_{i}.jpg"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(r.content)
                local_images.append(filename)

        # 2. Audio
        has_audio = False
        if audio_url:
            r_audio = requests.get(audio_url, timeout=10)
            if r_audio.status_code == 200:
                with open("audio.mp3", "wb") as f:
                    f.write(r_audio.content)
                has_audio = True

        # 3. List.txt
        with open("list.txt", "w") as f:
            for img in local_images:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration}\n")
            f.write(f"file '{local_images[-1]}'\n")

        # 4. FFmpeg con configuración de bajo consumo
        fps = 25
        total_frames = duration * fps * len(images) # Ajustado para 30 seg
        
        # Filtro ultra-optimizado para no morir en el intento
        video_filter = (
            f"scale=640:-1,zoompan=z='min(zoom+0.0015,1.25)':d={total_frames/len(images)}:s=720x1280:fps={fps},"
            "format=yuv420p"
        )

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt"]
        if has_audio: cmd += ["-i", "audio.mp3"]
        
        cmd += [
            "-vf", video_filter,
            "-vcodec", "libx264",
            "-preset", "ultrafast", # Velocidad máxima
            "-crf", "28",           # Comprime un poco más para ahorrar CPU
            "-pix_fmt", "yuv420p"
        ]
        
        if has_audio: cmd += ["-acodec", "aac", "-shortest"]
        cmd.append("output.mp4")

        subprocess.run(cmd)
        print("✅ Video de 30 segundos finalizado.")
        
    except Exception as e:
        print(f"❌ Error en proceso asíncrono: {e}")

@app.route("/render", methods=["POST"])
def render():
    data = request.get_json()
    images = data.get("images", [])
    duration = data.get("duration", 5) # Si son 6 imágenes, pon 5 seg cada una
    audio_url = data.get("audio")

    # 🚀 LANZAR EN SEGUNDO PLANO
    # Esto permite responderle a n8n en 1 milisegundo
    thread = threading.Thread(target=generar_video_async, args=(images, duration, audio_url))
    thread.start()

    return jsonify({
        "status": "processing",
        "message": "El video se está generando en segundo plano. Revisa /video en unos minutos."
    })

@app.route("/video", methods=["GET"])
def get_video():
    if os.path.exists("output.mp4"):
        return send_file("output.mp4", mimetype="video/mp4")
    return jsonify({"status": "error", "message": "Video no listo o procesándose"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
