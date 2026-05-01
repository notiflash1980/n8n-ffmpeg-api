from flask import Flask, request, jsonify, send_file
import json
import os

app = Flask(__name__)

@app.route("/render", methods=["POST"])
def render():
    data = request.json

    # guardar JSON
    with open("data.json", "w") as f:
        json.dump(data, f)

    images = data.get("images", [])
    duration = data.get("duration", 3)

    # generar list.txt
    with open("list.txt", "w") as f:
        for img in images:
            f.write(f"file '{img}'\n")
            f.write(f"duration {duration}\n")

        if images:
            f.write(f"file '{images[-1]}'\n")

    print("list.txt generado")

    # 🔥 EJECUTAR FFMPEG
    try:
        os.system("""
        ffmpeg -y -f concat -safe 0 -i list.txt \
        -vsync vfr -pix_fmt yuv420p output.mp4
        """)
        print("video generado")
    except Exception as e:
        print("error ffmpeg:", e)

    return jsonify({
        "status": "ok",
        "message": "video generado"
    })


# 🟣 NUEVO ENDPOINT PARA VER EL VIDEO
@app.route("/video", methods=["GET"])
def get_video():
    try:
        return send_file("output.mp4", mimetype="video/mp4")
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
