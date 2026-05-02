from flask import Flask, request, jsonify
import json
import os
import requests

app = Flask(__name__)

@app.route("/render", methods=["POST"])
def render():
    data = request.json

    images = data.get("images", [])
    duration = data.get("duration", 2)

    local_images = []

    # 🔽 DESCARGAR IMÁGENES
    for i, url in enumerate(images):
        filename = f"{i}.jpg"
        r = requests.get(url)
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
    os.system("""
ffmpeg -y -f concat -safe 0 -i list.txt \
-vf "fps=25,format=yuv420p" \
-vcodec libx264 output.mp4
""")

    return jsonify({
        "status": "ok",
        "message": "video generado"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
