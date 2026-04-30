FROM python:3.11

# instalar ffmpeg
RUN apt update && apt install -y ffmpeg

# carpeta de trabajo
WORKDIR /app

# copiar archivos
COPY . .

# instalar dependencias
RUN pip install -r requirements.txt

# ejecutar app
CMD ["python", "app.py"]
