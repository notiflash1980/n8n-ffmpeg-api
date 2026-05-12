import os
import subprocess
import threading
import asyncio
from flask import Flask, request, jsonify
import requests
import urllib.parse
import random
import edge_tts

app = Flask(__name__)

# URL de tu Webhook de Producción en n8n
N8N_WEBHOOK_URL = "https://n8n-hv24.onrender.com/webhook/video-listo"

async def generar_voz_masculina(texto, archivo_salida):
    """Usa una voz masculina potente (Alvaro) de Microsoft Edge"""
    communicate = edge_tts.Communicate(texto, "es-ES-AlvaroNeural")
    await communicate.save(archivo_salida)

def procesar_video_en_background(escenas):
    archivos_mp4 = []
    
    try:
        for i, escena in enumerate(escenas):
            prompt = escena.get('titulo', '')
            texto = escena.get('subtitulo', '')
            
            # 1. AUDIO MASCULINO
            audio_file = f"audio_{i}.mp3"
            asyncio.run(generar_voz_masculina(texto, audio_file))

            # 2. IMAGEN VERTICAL
            url_imagen = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1080&height=1920&nologo=true"
            img_file = f"img_{i}.jpg"
            r = requests.get(url_imagen)
            with open(img_file, 'wb') as f:
                f.write(r.content)

            # 3. RENDER ESCENA (VERTICAL 9:16 + SUBTÍTULOS ELEGANTES)
            scene_file = f"scene_{i}.mp4"
            archivos_mp4.append(scene_file)
            
            texto_limpio = texto.replace("'", "").replace(":", "\\:")
            
            # Estilo de subtítulo: Blanco, borde negro, sombra, centrado abajo con margen
            style = (
                "drawtext=text='{0}':fontcolor=white:fontsize=54:x=(w-text_w)/2:y=h-450:"
                "borderw=3:bordercolor=black:shadowcolor=black@0.5:shadowx=4:shadowy=4:"
                "fix_bounds=1" # Esto evita que el texto se salga de los bordes
            ).format(texto_limpio)

            cmd_escena = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", "25", "-i", img_file,
                "-i", audio_file,
                "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{style},format=yuv420p",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                scene_file
            ]
            subprocess.run(cmd_escena, check=True)

        # 4. UNIR TODO
        with open("list.txt", "w") as f:
            for mp4 in archivos_mp4:
                f.write(f"file '{mp4}'\n")

        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
            "-c", "copy", "output_final.mp4"
        ]
        subprocess.run(cmd_concat, check=True)

        # 5. ENVIAR
        with open("output_final.mp4", "rb") as video_file:
            files = {'video': ('video_final.mp4', video_file, 'video/mp4')}
            requests.post(N8N_WEBHOOK_URL, files=files)

    except Exception as e:
        print(f"Error: {e}")

@app.route('/render', methods=['POST'])
def generar_video():
    data = request.json
    escenas = data.get('lista_escenas', [])
    if not escenas:
        return jsonify({"error": "No escenas"}), 400

    threading.Thread(target=procesar_video_en_background, args=(escenas,)).start()
    return jsonify({"status": "Cocinando video vertical masculino..."}), 202

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
