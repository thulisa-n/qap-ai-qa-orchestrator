FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY app/requirements.txt /workspace/app/requirements.txt
RUN pip install --no-cache-dir -r /workspace/app/requirements.txt

COPY app /workspace/app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.src.app:app", "--host", "0.0.0.0", "--port", "8000"]
