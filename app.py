import os
import subprocess
import threading
import asyncio
import textwrap
from flask import Flask, request, jsonify
import requests
import urllib.parse
import random
import edge_tts

app = Flask(__name__)

N8N_WEBHOOK_URL = "https://n8n-hv24.onrender.com/webhook/video-listo"

async def generar_voz_masculina(texto, archivo_salida):
    """Voz de Álvaro con velocidad aumentada (+15%)"""
    # 'rate=+15%' hace que hable más fluido y menos pausado
    communicate = edge_tts.Communicate(texto, "es-ES-AlvaroNeural", rate="+15%")
    await communicate.save(archivo_salida)

def procesar_video_en_background(escenas):
    archivos_mp4 = []
    
    try:
        print(f"🎬 Iniciando producción de {len(escenas)} escenas...")
        for i, escena in enumerate(escenas):
            prompt = escena.get('titulo', '')
            texto = escena.get('subtitulo', '')
            
            # --- 1. AUDIO (Más rápido) ---
            audio_file = f"audio_{i}.mp3"
            asyncio.run(generar_voz_masculina(texto, audio_file))

            # --- 2. IMAGEN ---
            url_imagen = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1080&height=1920&nologo=true"
            img_file = f"img_{i}.jpg"
            r = requests.get(url_imagen)
            with open(img_file, 'wb') as f:
                f.write(r.content)

            # --- 3. PROCESAR TEXTO (Salto de línea automático) ---
            # Cortamos el texto cada 30 caracteres para que no se salga de la pantalla
            texto_con_saltos = "\n".join(textwrap.wrap(texto, width=30))
            texto_limpio = texto_con_saltos.replace("'", "").replace(":", "\\:")

            # --- 4. MOVIMIENTO DE CÁMARA ---
            efectos = [
                "zoompan=z='min(zoom+0.0015,1.5)':d=300:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1080x1920",
                "zoompan=z=1.2:d=300:x='x+0.8':y='ih/2-(ih/zoom)/2':s=1080x1920",
                "zoompan=z=1.2:d=300:x='x-0.8':y='ih/2-(ih/zoom)/2':s=1080x1920"
            ]
            efecto_elegido = random.choice(efectos)

            # --- 5. RENDER (Estilo de Subtítulo Mejorado) ---
            scene_file = f"scene_{i}.mp4"
            archivos_mp4.append(scene_file)
            
            # Nuevo estilo: Texto más grande, borde grueso (5), sombra y margen de seguridad (y=h-500)
            style = (
                f"drawtext=text='{texto_limpio}':fontcolor=white:fontsize=65:x=(w-text_w)/2:y=h-600:"
                f"borderw=4:bordercolor=black@0.8:shadowcolor=black@0.5:shadowx=4:shadowy=4:line_spacing=10"
            )

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
            print(f"✅ Escena {i} lista.")

        # --- 6. UNIR Y ENVIAR ---
        print("🧩 Uniendo video final...")
        with open("list.txt", "w") as f:
            for mp4 in archivos_mp4:
                f.write(f"file '{mp4}'\n")

        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
            "-c", "copy", "output_final.mp4"
        ]
        subprocess.run(cmd_concat, check=True)

        with open("output_final.mp4", "rb") as video_file:
            requests.post(N8N_WEBHOOK_URL, files={'video': ('video.mp4', video_file, 'video/mp4')})
        print("🚀 Video enviado con éxito.")

    except Exception as e:
        print(f"❌ Error catastrófico: {e}")

@app.route('/render', methods=['POST'])
def generar_video():
    data = request.json
    escenas = data.get('lista_escenas', [])
    if not escenas: return jsonify({"error": "No data"}), 400
    threading.Thread(target=procesar_video_en_background, args=(escenas,)).start()
    return jsonify({"status": f"Procesando {len(escenas)} escenas con Álvaro Veloz..."}), 202

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
