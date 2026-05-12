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

# 👇 Tu URL de Producción confirmada 👇
N8N_WEBHOOK_URL = "https://n8n-hv24.onrender.com/webhook/video-listo"

async def generar_voz_masculina(texto, archivo_salida):
    """Voz premium de Microsoft Edge (Álvaro)"""
    communicate = edge_tts.Communicate(texto, "es-ES-AlvaroNeural")
    await communicate.save(archivo_salida)

def procesar_video_en_background(escenas):
    archivos_mp4 = []
    
    try:
        print("🔄 Iniciando FASE 1: Producción Vertical Nativa...")
        for i, escena in enumerate(escenas):
            prompt = escena.get('titulo', '')
            texto = escena.get('subtitulo', '')
            
            # --- 1. AUDIO (Álvaro) ---
            audio_file = f"audio_{i}.mp3"
            asyncio.run(generar_voz_masculina(texto, audio_file))

            # --- 2. IMAGEN (Generación Nativa 9:16 desde Pollinations) ---
            url_imagen = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1080&height=1920&nologo=true"
            img_file = f"img_{i}.jpg"
            r = requests.get(url_imagen)
            with open(img_file, 'wb') as f:
                f.write(r.content)

            # --- 3. MOVIMIENTO DE CÁMARA (Forzando salida Vertical s=1080x1920) ---
            efectos = [
                "zoompan=z='min(zoom+0.0015,1.5)':d=300:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1080x1920", # Zoom In
                "zoompan=z=1.2:d=300:x='x+1':y='ih/2-(ih/zoom)/2':s=1080x1920", # Pan Derecha
                "zoompan=z=1.2:d=300:x='x-1':y='ih/2-(ih/zoom)/2':s=1080x1920"  # Pan Izquierda
            ]
            efecto_elegido = random.choice(efectos)

            # --- 4. RENDER CON SUBTÍTULOS ESTILO CINE ---
            scene_file = f"scene_{i}.mp4"
            archivos_mp4.append(scene_file)
            
            texto_limpio = texto.replace("'", "").replace(":", "\\:")
            
            # Diseño: Letra blanca, borde negro grosor 3, sombra suave, posicionado abajo.
            style = (
                "drawtext=text='{0}':fontcolor=white:fontsize=50:x=(w-text_w)/2:y=h-(h/5):"
                "borderw=3:bordercolor=black:shadowcolor=black@0.6:shadowx=4:shadowy=4"
            ).format(texto_limpio)

            cmd_escena = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", "25", "-i", img_file,
                "-i", audio_file,
                "-vf", f"format=yuv420p,{efecto_elegido},{style}",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                scene_file
            ]
            subprocess.run(cmd_escena, check=True)
            print(f"✅ Escena {i} vertical lista.")

        # --- 5. UNIR TODO ---
        print("🧩 Uniendo archivo final...")
        with open("list.txt", "w") as f:
            for mp4 in archivos_mp4:
                f.write(f"file '{mp4}'\n")

        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
            "-c", "copy", "output_final.mp4"
        ]
        subprocess.run(cmd_concat, check=True)

        # --- 6. ENVIAR A N8N ---
        with open("output_final.mp4", "rb") as video_file:
            files = {'video': ('video_final.mp4', video_file, 'video/mp4')}
            requests.post(N8N_WEBHOOK_URL, files=files)
        print("🚀 Video enviado a Telegram.")

    except Exception as e:
        print(f"❌ Error: {e}")

@app.route('/render', methods=['POST'])
def generar_video():
    data = request.json
    escenas = data.get('lista_escenas', [])
    if not escenas:
        return jsonify({"error": "No escenas"}), 400

    threading.Thread(target=procesar_video_en_background, args=(escenas,)).start()
    return jsonify({"status": "Cocinando..."}), 202

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
