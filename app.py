import os
import subprocess
import threading
from flask import Flask, request, jsonify
import requests
import urllib.parse
import random
from gtts import gTTS

app = Flask(__name__)

# 👇 PON AQUÍ LA URL TEST DE TU NUEVO NODO WEBHOOK EN N8N 👇
N8N_WEBHOOK_URL = "https://n8n-hv24.onrender.com/webhook-test/video-listo"

def procesar_video_en_background(escenas):
    """Esta función hace el trabajo pesado sin bloquear a n8n"""
    archivos_mp4 = []
    archivos_mp3 = []
    archivos_jpg = []

    try:
        print("🔄 [FASE 1] Iniciando fabricación de mini-videos...")

        for i, escena in enumerate(escenas):
            prompt = escena.get('titulo', '')
            texto = escena.get('subtitulo', '')
            
            # --- 1. GENERAR AUDIO (gTTS) ---
            print(f"🎙️ Generando audio {i}...")
            tts = gTTS(text=texto, lang='es')
            audio_file = f"audio_{i}.mp3"
            tts.save(audio_file)
            archivos_mp3.append(audio_file)

            # --- 2. DESCARGAR IMAGEN ---
            print(f"🖼️ Descargando imagen {i}...")
            url_imagen = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1080&height=1920&nologo=true"
            img_file = f"img_{i}.jpg"
            r = requests.get(url_imagen)
            with open(img_file, 'wb') as f:
                f.write(r.content)
            archivos_jpg.append(img_file)

            # --- 3. RULETA DE EFECTOS DE CÁMARA ---
            # d=300 significa 12 segundos máximos. El video se cortará antes gracias al audio.
            efectos = [
                "zoompan=z='min(zoom+0.0015,1.5)':d=300:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2'", # Zoom In Centro
                "zoompan=z=1.2:d=300:x='x+1':y='ih/2-(ih/zoom)/2'", # Pan Derecha
                "zoompan=z=1.2:d=300:x='x-1':y='ih/2-(ih/zoom)/2'"  # Pan Izquierda
            ]
            efecto_elegido = random.choice(efectos)

            # --- 4. RENDERIZAR MINI-VIDEO CON SUBTÍTULOS ---
            print(f"🎬 Renderizando escena {i} con efecto aleatorio...")
            scene_file = f"scene_{i}.mp4"
            archivos_mp4.append(scene_file)
            
            # Limpiamos el texto de comillas para no romper FFmpeg
            texto_limpio = texto.replace("'", "").replace(":", "\\:")

            cmd_escena = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", "25", "-i", img_file,
                "-i", audio_file,
                "-vf", f"scale=-2:1080,format=yuv420p,{efecto_elegido},drawtext=text='{texto_limpio}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-(h/4):box=1:boxcolor=black@0.6:boxborderw=10",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest", # TRUCO DE MAGIA: Corta el video exactamente cuando termina el audio de gTTS
                scene_file
            ]
            subprocess.run(cmd_escena, check=True)
            print(f"✅ Escena {i} completada.")

        # --- 5. UNIR TODOS LOS MINI-VIDEOS ---
        print("🧩 [FASE 2] Uniendo las escenas...")
        with open("list.txt", "w") as f:
            for mp4 in archivos_mp4:
                f.write(f"file '{mp4}'\n")

        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
            "-c", "copy", "output_final.mp4"
        ]
        subprocess.run(cmd_concat, check=True)
        print("🏆 ¡VIDEO FINAL GENERADO CON ÉXITO!")

        # --- 6. ENVIAR A N8N (EL REPARTIDOR) ---
        print("📬 Enviando video al Webhook de n8n...")
        with open("output_final.mp4", "rb") as video_file:
            files = {'video': ('video_final.mp4', video_file, 'video/mp4')}
            requests.post(N8N_WEBHOOK_URL, files=files)
        print("🚀 ¡Envío completado!")

    except Exception as e:
        print(f"❌ Error catastrófico en el background: {e}")

@app.route('/render', methods=['POST'])
def generar_video():
    """Recibe la orden de n8n y suelta la conexión al instante"""
    data = request.json
    escenas = data.get('lista_escenas', [])
    
    if not escenas:
        return jsonify({"error": "No se encontró la lista_escenas"}), 400

    # Lanzamos el trabajo pesado en un hilo separado
    hilo = threading.Thread(target=procesar_video_en_background, args=(escenas,))
    hilo.start()

    # Le decimos a n8n: "Mensaje recibido, yo me encargo, ya te puedes ir"
    return jsonify({"status": "Procesamiento iniciado. Te avisaré al Webhook cuando termine."}), 202

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
