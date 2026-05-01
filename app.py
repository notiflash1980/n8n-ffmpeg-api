from flask import Flask, request, jsonify, send_file
import json
import os

app = Flask(__name__)

@app.route("/render", methods=["POST"])
def render():
    data = request.json

    # guardar JSON
    with open("/app/data.json", "w") as f:
        json.dump(data, f)

    images = data.get("images", [])
    duration = data.get("duration", 3)

    # generar list.txt
    with open("/app/list.txt", "w") as f:
        for img in images:
            f.write(f"file '{img}'\n")
            f.write(f"duration {duration}\n")

        if images:
            f.write(f"file '{images[-1]}'\n")

    print("list.txt generado")

    # 🔥 VERIFICAR Y EJECUTAR FFMPEG (CORREGIDO)
    print("verificando list.txt:", os.path.exists("/app/list.txt"))

    if os.path.exists("/app/list.txt"):
        cmd = "ffmpeg -y -f concat -safe 0 -i /app/list.txt -vsync vfr -pix_fmt yuv420p /app/output.mp4"
        print("ejecutando:", cmd)
        os.system(cmd)
    else:
        print("ERROR: list.txt no existe")

    return jsonify({
        "status": "ok",
        "message": "proceso ejecutado"
    })


# 🟣 ENDPOINT PARA VER EL VIDEO
@app.route("/video", methods=["GET"])
def get_video():
    try:
        return send_file("/app/output.mp4", mimetype="video/mp4")
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
