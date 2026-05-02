from flask import Flask, request, jsonify, send_file
import json
import os
import requests

app = Flask(__name__)

@app.route("/render", methods=["POST"])
def render():
    try:
        data = request.json

        images = data.get("images", [])
        duration = data.get("duration", 2)

        local_images = []

        # 🔽 DESCARGAR IMÁGENES
        for i, url in enumerate(images):
            filename = f"{i}.jpg"
            r = requests.get(url)

            if r.status_code != 200:
                return jsonify({
                    "status": "error",
                    "message": f"error descargando {url}"
                })

            with open(filename, "wb") as f:
                f.write(r.content)

            local_images.append(filename)

        # 📝 CREAR list.txt
        with open("list.txt", "w") as f:
            for img in local_images:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration}\n")

            if local_images:
                f.write(f"file '{local_images[-1]}'\n")

        # 🎬 GENERAR VIDEO
        result = os.system("""
audio_url = data.get("audio")

if audio_url:
    r = requests.get(audio_url)
    with open("audio.mp3", "wb") as f:
        f.write(r.content)
ffmpeg -y -f concat -safe 0 -i list.txt \
-vf "fps=25,format=yuv420p" \
-vcodec libx264 \
-i audio.mp3 -shortest \
output.mp4
""")

        if result != 0:
            return jsonify({
                "status": "error",
                "message": "fallo en ffmpeg"
            })

        return jsonify({
            "status": "ok",
            "message": "video generado"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


# 🔥 NUEVA RUTA PARA VER EL VIDEO
@app.route("/video", methods=["GET"])
def get_video():
    if os.path.exists("output.mp4"):
        return send_file("output.mp4", mimetype="video/mp4")
    else:
        return jsonify({
            "status": "error",
            "message": "video no existe aún"
        })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
