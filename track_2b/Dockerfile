# Polyglot Explainer — Hack Apertus Track 2B
# Judges run `make run` from track_2b/ (the project root) on a clean checkout.
# Runs end-to-end in Docker with NO API key (clearly-labeled demo mode).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 5000

# gunicorn imports src.app (the Flask instance) — the `debug=True` dev server
# in app.py's __main__ block is never used here.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", \
     "--timeout", "120", "src.app:app"]
