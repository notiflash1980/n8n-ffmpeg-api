import os

@app.route("/render", methods=["POST"])
def render():
    data = request.json

    images = data.get("images", [])
    duration = data.get("duration", 3)

    # crear list.txt
    with open("list.txt", "w") as f:
        for img in images:
            f.write(f"file '{img}'\n")
            f.write(f"duration {duration}\n")
        if images:
            f.write(f"file '{images[-1]}'\n")

    # 🔥 EJECUTAR FFMPEG
    os.system("""
        ffmpeg -y -f concat -safe 0 -i list.txt \
        -vsync vfr -pix_fmt yuv420p output.mp4
    """)

    return {
        "status": "ok",
        "message": "video generado"
    }
