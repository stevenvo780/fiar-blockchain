# 1. Usar una imagen base de Python ligera
FROM python:3.10-slim

# 2. Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Establecer el directorio de trabajo
WORKDIR /app

# 4. Instalar dependencias
# Copiar solo el archivo de requerimientos primero para aprovechar el caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copiar el código de la aplicación
COPY app.py .

# 6. Exponer el puerto (opcional para Cloud Run, pero buena práctica)
# Cloud Run ignora EXPOSE y usa la variable PORT
EXPOSE 8080

# 7. Comando para ejecutar la aplicación
# Usar la variable de entorno PORT proporcionada por Cloud Run
# El script de shell 'sh -c' permite la sustitución de variables de entorno
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port $PORT"]
