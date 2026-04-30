from flask import Flask, request, jsonify
import json

app = Flask(__name__)

@app.route("/render", methods=["POST"])
def render():
    data = request.json

    # guardar JSON recibido
    with open("data.json", "w") as f:
        json.dump(data, f)

    print("JSON guardado correctamente")

    return jsonify({
        "status": "ok",
        "message": "json guardado"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
