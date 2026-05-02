from flask import Flask, request, jsonify, send_file
import os
import requests

app = Flask(__name__)

@app.route("/render", methods=["POST"])
def render():
    try:
        data = request.json
        images = data.get("images", [])
        duration = data.get("duration", 2)
        audio_url = data.get("audio")  # 🟢 Capturamos la URL del audio

        local_images = []

        # 🔽 1. DESCARGAR IMÁGENES
        for i, url in enumerate(images):
            filename = f"{i}.jpg"
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return jsonify({"status": "error", "message": f"error descargando {url}"})
            with open(filename, "wb") as f:
                f.write(r.content)
            local_images.append(filename)

        # 🔽 2. DESCARGAR AUDIO (Si se envía en el JSON)
        has_audio = False
        audio_filename = "audio.mp3"
        if audio_url:
            r_audio = requests.get(audio_url, timeout=15)
            if r_audio.status_code == 200:
                with open(audio_filename, "wb") as f:
                    f.write(r_audio.content)
                has_audio = True

        # 📝 3. CREAR list.txt
        with open("list.txt", "w") as f:
            for img in local_images:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration}\n")
            if local_images:
                f.write(f"file '{local_images[-1]}'\n")

        # 🎬 4. GENERAR VIDEO (FFmpeg dinámico)
        # scale=trunc(iw/2)*2:trunc(ih/2)*2 evita errores si la imagen es impar
        if has_audio:
            # Comando con AUDIO
            cmd = f"""
            ffmpeg -y -f concat -safe 0 -i list.txt -i {audio_filename} \
            -vf "fps=25,format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2" \
            -vcodec libx264 -acodec aac -shortest output.mp4
            """
        else:
            # Comando sin AUDIO (mudo)
            cmd = """
            ffmpeg -y -f concat -safe 0 -i list.txt \
            -vf "fps=25,format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2" \
            -vcodec libx264 output.mp4
            """

        result = os.system(cmd)

        if result != 0:
            return jsonify({"status": "error", "message": "fallo en ffmpeg"})

        return jsonify({
            "status": "ok", 
            "message": "video generado", 
            "audio": has_audio
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# 🔥 RUTA PARA VER EL VIDEO
@app.route("/video", methods=["GET"])
def get_video():
    if os.path.exists("output.mp4"):
        return send_file("output.mp4", mimetype="video/mp4")
    else:
        return jsonify({"status": "error", "message": "video no existe aún"}), 404

if __name__ == "__main__":
    # Importante: Render usa la variable PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
