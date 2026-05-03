# ... (todo lo demás igual arriba)

def generar_video_async(images, duration, audio_url):
    try:
        # 1. Limpieza de archivos viejos al empezar
        for f in ["output.mp4", "list.txt", "audio.mp3"]:
            if os.path.exists(f): os.remove(f)

        local_images = []
        for i, url in enumerate(images):
            filename = f"img_{i}.jpg"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(filename, "wb") as f: f.write(r.content)
                local_images.append(filename)

        # 2. Audio
        has_audio = False
        if audio_url:
            r_audio = requests.get(audio_url, timeout=10)
            if r_audio.status_code == 200:
                with open("audio.mp3", "wb") as f: f.write(r_audio.content)
                has_audio = True

        # 3. Crear list.txt
        with open("list.txt", "w") as f:
            for img in local_images:
                f.write(f"file '{img}'\n")
                f.write(f"duration {duration}\n")
            f.write(f"file '{local_images[-1]}'\n")

        # 4. FFmpeg "MODO AHORRO DE RAM"
        # Bajamos scale a 400 para que la RAM no explote en 30 segundos
        fps = 25
        total_frames_per_img = duration * fps
        
        video_filter = (
            f"scale=400:-1,zoompan=z='min(zoom+0.0015,1.25)':d={total_frames_per_img}:s=720x1280:fps={fps},"
            "format=yuv420p"
        )

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt"
        ]
        if has_audio: cmd += ["-i", "audio.mp3"]

        cmd += [
            "-vf", video_filter,
            "-vcodec", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-threads", "1", # 👈 Limitamos a 1 solo núcleo para no saturar Render
            "-pix_fmt", "yuv420p"
        ]

        if has_audio: cmd += ["-acodec", "aac", "-shortest"]
        cmd.append("output.mp4")

        # Ejecutar y capturar el error en el log de Render
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ FFMPEG ERROR LOG: {result.stderr}")
        else:
            print("✅ VIDEO GENERADO CON ÉXITO")

    except Exception as e:
        print(f"❌ Error crítico: {e}")

# ... (resto del código igual)
