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
    async def _async_run():
        communicate = edge_tts.Communicate(texto, "es-MX-JorgeNeural", rate="+20%")
        await communicate.save(archivo_salida)
    asyncio.run(_async_run())

def procesar_video_en_background(escenas):
    archivos_mp4 = []
    # 1. CREAMOS LA LISTA MAESTRA DE LIMPIEZA
    archivos_a_borrar = ["list.txt", "output_final.mp4"]
    
    try:
        print(f"🎬 Iniciando producción de {len(escenas)} escenas...")
        
        for i, escena in enumerate(escenas):
            prompt = escena.get('titulo', '')
            texto = escena.get('subtitulo', '')
            
            # Nombramos los archivos
            audio_file = f"audio_{i}.mp3"
            img_file = f"img_{i}.jpg"
            txt_file = f"subtitulo_{i}.txt"
            scene_file = f"scene_{i}.mp4"

            # 2. LOS AGREGAMOS AL REGISTRO DE LIMPIEZA INMEDIATAMENTE
            archivos_a_borrar.extend([audio_file, img_file, txt_file, scene_file])
            
            # 1. AUDIO
            generar_voz_sincrona(texto, audio_file)

            # 2. IMAGEN SEGURA CON REINTENTOS
            url_imagen = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1080&height=1920&nologo=true"
            print(f"📸 Solicita escena {i}: {url_imagen}")
            
            max_reintentos = 3
            imagen_valida = False
            
            for intento in range(max_reintentos):
                try:
                    r = requests.get(url_imagen, timeout=30)
                    # Verificamos código 200 y que realmente sea un archivo de imagen
                    if r.status_code == 200 and 'image' in r.headers.get('Content-Type', ''):
                        with open(img_file, 'wb') as f:
                            f.write(r.content)
                        
                        # Validamos que el archivo tenga un peso lógico (> 5KB)
                        if os.path.getsize(img_file) > 5000:
                            imagen_valida = True
                            break
                        else:
                            print(f"⚠️ Imagen corrupta o muy pequeña. Reintentando...")
                    else:
                        print(f"⚠️ Servidor Pollinations ocupado (Código {r.status_code}). Intento {intento+1}/{max_reintentos}...")
                
                except requests.exceptions.RequestException as e:
                    print(f"⚠️ Error de red al descargar imagen: {e}")
                
                time.sleep(3) # Esperamos 3 segundos antes del próximo intento
                
            if not imagen_valida:
                raise Exception(f"Imposible obtener una imagen válida de Pollinations para la escena {i} después de {max_reintentos} intentos.")

            # 3. TEXTO
            texto_con_saltos = "\n".join(textwrap.wrap(texto, width=28))
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(texto_con_saltos)

            # 4. MOVIMIENTO
            efectos = [
                "zoompan=z='min(zoom+0.0015,1.5)':d=300:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1080x1920",
                "zoompan=z=1.2:d=300:x='x+0.8':y='ih/2-(ih/zoom)/2':s=1080x1920",
                "zoompan=z=1.2:d=300:x='x-0.8':y='ih/2-(ih/zoom)/2':s=1080x1920"
            ]
            efecto_elegido = random.choice(efectos)

            # 5. RENDER CON FILTRO SILENCEREMOVE
            archivos_mp4.append(scene_file)
            
            cmd_escena = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", "25", "-i", img_file,
                "-i", audio_file,
                "-vf", f"format=yuv420p,{efecto_elegido}",
                "-af", "silenceremove=stop_periods=-1:stop_duration=0.1:stop_threshold=-40dB",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                scene_file
            ]
            
            subprocess.run(cmd_escena, check=True)
            print(f"scene_{i}.mp4 generada")

        # 6. CONCATENAR
        print("🧩 Juntando todas las escenas y limpiando tiempos...")
        with open("list.txt", "w") as f:
            for mp4 in archivos_mp4:
                f.write(f"file '{mp4}'\n")

        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "output_final.mp4"
        ]
        subprocess.run(cmd_concat, check=True)

        # 7. ENVIAR A N8N
        with open("output_final.mp4", "rb") as video_file:
            requests.post(N8N_WEBHOOK_URL, files={'video': ('video.mp4', video_file, 'video/mp4')})
        print("🚀 ¡Video enviado a n8n!")

    except Exception as e:
        print(f"❌ Error en el procesamiento: {e}")

    finally:
        # 3. BLOQUE FINALLY: Esta sección se ejecuta SIEMPRE, incluso si hubo un error.
        print("🧹 Iniciando limpieza de servidor...")
        for f_temp in archivos_a_borrar:
            if os.path.exists(f_temp):
                try: 
                    os.remove(f_temp)
                except Exception as ex: 
                    print(f"⚠️ No se pudo borrar {f_temp}: {ex}")
        print("✨ Limpieza completada.")

@app.route('/render', methods=['POST'])
def generar_video():
    data = request.json
    escenas = data.get('lista_escenas', [])
    if not escenas: 
        return jsonify({"error": "No data"}), 400
        
    threading.Thread(target=procesar_video_en_background, args=(escenas,)).start()
    return jsonify({"status": "Procesando nuevo estilo..."}), 202

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
