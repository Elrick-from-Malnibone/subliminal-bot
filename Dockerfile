FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libatomic1 \
    libsndfile1 \
    libgomp1 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Проверка импортов — покажет, где падает
RUN python -c "import aiogram; print('aiogram OK')" || echo "AIOGRAM FAILED"
RUN python -c "import pydub; print('pydub OK')" || echo "PYDUB FAILED"
RUN python -c "import pedalboard; print('pedalboard OK')" || echo "PEDALBOARD FAILED"
RUN python -c "from services.audio import create_subliminal; print('audio OK')" || echo "AUDIO FAILED"

COPY . .

CMD ["python", "-u", "main.py"]