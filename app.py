import os
import subprocess
import threading
import asyncio
import textwrap
import time
from flask import Flask, request, jsonify
import requests
import urllib.parse
import random
import edge_tts

app = Flask(__name__)

N8N_WEBHOOK_URL = "https://n8n-hv24.onrender.com/webhook/video-listo"

def generar_voz_sincrona(texto, archivo_salida):
    """Ejecuta edge-tts de forma aislada y limpia para evitar fugas de memoria"""
    async def _async_run():
        communicate = edge_tts.Communicate(texto, "es-MX-JorgeNeural", rate="+15%")
        await communicate.save(archivo_salida)
    
    # Creamos y cerramos el bucle en una sola línea segura
    asyncio.run(_async_run())

def procesar_video_en_background(escenas):
    """Línea de montaje síncrona, limpia y segura para la RAM de Render"""
    archivos_mp4 = []
    
    try:
        print(f"🎬 Iniciando producción de {len(escenas)} escenas...")
        
        for i, escena in enumerate(escenas):
            prompt = escena.get('titulo', '')
            texto = escena.get('subtitulo', '')
            
            # --- 1. AUDIO ---
            audio_file = f"audio_{i}.mp3"
            generar_voz_sincrona(texto, audio_file)

            # --- 2. IMAGEN CON SISTEMA ANTI-BLOQUEO ---
            img_file = f"img_{i}.jpg"
            url_imagen = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1080&height=1920&nologo=true"
            
            print(f"📸 Solicitando imagen {i} a la IA...")
            r = requests.get(url_imagen)
            
            # Verificación de imagen corrupta (Rueda de repuesto)
            if r.status_code != 200 or b"JFIF" not in r.content[:100] and b"ffd8" not in r.content.hex()[:10]:
                print(f"⚠️ Pollinations rechazó la escena {i}. Activando imagen de emergencia...")
                url_emergencia = "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1080&h=1920&fit=crop"
                r = requests.get(url_emergencia)

            with open(img_file, 'wb') as f:
                f.write(r.content)

            # --- 3. TEXTO ---
            texto_con_saltos = "\n".join(textwrap.wrap(texto, width=28))
            txt_file = f"subtitulo_{i}.txt"
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(texto_con_saltos)

            # --- 4. MOVIMIENTO DE CÁMARA ---
            efectos = [
                "zoompan=z='min(zoom+0.0015,1.5)':d=300:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1080x1920",
                "zoompan=z=1.2:d=300:x='x+0.8':y='ih/2-(ih/zoom)/2':s=1080x1920",
                "zoompan=z=1.2:d=300:x='x-0.8':y='ih/2-(ih/zoom)/2':s=1080x1920"
            ]
            efecto_elegido = random.choice(efectos)

            # --- 5. RENDER ---
            scene_file = f"scene_{i}.mp4"
            archivos_mp4.append(scene_file)
            
            cmd_escena = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", "25", "-i", img_file,
                "-i", audio_file,
                "-vf", f"format=yuv420p,{efecto_elegido}",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                scene_file
            ]
            
            subprocess.run(cmd_escena, check=True)
            print(f"✅ Escena {i} lista y empaquetada.")
            
            # Pausa anti-bloqueo
            time.sleep(4)

        # --- 6. UNIR LAS PIEZAS ---
        print("🧩 Concatonando master final...")
        with open("list.txt", "w") as f:
            for mp4 in archivos_mp4:
                f.write(f"file '{mp4}'\n")

        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
            "-c", "copy", "output_final.mp4"
        ]
        subprocess.run(cmd_concat, check=True)

        # --- 7. ENVIAR EL PRODUCTO ---
        with open("output_final.mp4", "rb") as video_file:
            requests.post(N8N_WEBHOOK_URL, files={'video': ('video.mp4', video_file, 'video/mp4')})
        print("🚀 ¡Video enviado a n8n con éxito!")

    except Exception as e:
        print(f"❌ Error catastrófico en la línea de montaje: {e}")

@app.route('/render', methods=['POST'])
def generar_video():
    data = request.json
    escenas = data.get('lista_escenas', [])
    if not escenas: 
        return jsonify({"error": "No data"}), 400
        
    # Volvemos al método de hilo síncrono nativo que Render sí acepta perfectamente
    threading.Thread(target=procesar_video_en_background, args=(escenas,)).start()
    return jsonify({"status": "Procesando nuevo estilo..."}), 202

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
