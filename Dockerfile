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

# 6. Exponer el puerto en el que corre la aplicación
EXPOSE 8000

# 7. Comando para ejecutar la aplicación
# Cloud Run inyectará la variable de entorno PORT (usualmente 8080)
# y mapeará ese puerto externo al puerto 8000 expuesto por el contenedor.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
