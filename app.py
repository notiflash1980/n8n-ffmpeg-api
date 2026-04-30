from flask import Flask, request, jsonify
import json

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

    return jsonify({
        "status": "ok",
        "message": "list.txt generado"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
