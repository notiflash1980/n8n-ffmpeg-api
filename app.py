from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/render", methods=["POST"])
def render():
    data = request.json

    print("Recibido:", data)

    return jsonify({
        "status": "ok",
        "message": "endpoint render funcionando"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
