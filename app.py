from flask import Flask, request, jsonify, send_file
import os
import requests
import subprocess

app = Flask(__name__)

@app.route("/render", methods=["POST"])
def render():
    try:
        # Limpieza inicial de archivos de pruebas anteriores
        for f in ["output.mp4", "list.txt", "audio.mp3"]:
            if os.path.exists(f): os.remove(f)

        data = request.get_json()
        images = data.get("images", [])
        duration = data.get("duration", 2)
        audio_url = data.get("audio")

        local_images = []

        # 🔽 1. DESCARGAR IMÁGENES
        for i, url in enumerate(images):
            filename = f"img_{i}.jpg"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(r.content)
                local_images.append(filename)

        if not local_images:
            return jsonify({"status": "error", "message": "No hay imágenes"}), 400

        # 🔽 2. DESCARGAR AUDIO
        has_audio = False
        if audio_url:
            try:
                r_audio = requests.get(audio_url, timeout=10)
                if r_audio.status_code == 200:
                    with open("audio.mp3", "wb") as f:
                        f.write(r_audio.content)
                    has_audio = True
            except:
                pass

        # 📝 3. CREAR list.txt
        with open("list.txt", "w") as f:
            for img in local_images:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration}\n")
            f.write(f"file '{local_images[-1]}'\n")

        # 🎬 4. GENERAR VIDEO (Versión Optimizada para Render Gratis)
        # Explicación: scale ajusta el ancho, luego zoompan mueve, y al final forzamos vertical 720x1280.
        fps = 25
        total_frames = duration * fps
        
        # Filtro simplificado: menos carga de CPU
        video_filter = (
            f"scale=800:-1,zoompan=z='min(zoom+0.0015,1.25)':d={total_frames}:s=720x1280:fps={fps},"
            "format=yuv420p"
        )

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt"
        ]
        
        if has_audio:
            cmd += ["-i", "audio.mp3"]

        cmd += [
            "-vf", video_filter,
            "-vcodec", "libx264",
            "-preset", "ultrafast",  # <--- CLAVE PARA RENDER
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p"
        ]

        if has_audio:
            cmd += ["-acodec", "aac", "-shortest"]

        cmd.append("output.mp4")

        # Ejecutamos y capturamos errores
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print("FFmpeg Error:", result.stderr)
            return jsonify({"status": "error", "error": "FFmpeg falló"}), 500

        return jsonify({"status": "ok", "message": "Video generado con éxito"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/video", methods=["GET"])
def get_video():
    if os.path.exists("output.mp4"):
        return send_file("output.mp4", mimetype="video/mp4")
    return jsonify({"error": "Video no encontrado"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
