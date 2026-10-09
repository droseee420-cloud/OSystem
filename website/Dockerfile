FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 site
COPY --chown=site:site public ./public
COPY --chown=site:site server.py routes.json ./
RUN mkdir -p /app/data && chown site:site /app/data
USER site
ENV PYTHONUNBUFFERED=1 DATA_DIR=/app/data
EXPOSE 8080
CMD ["waitress-serve", "--host=0.0.0.0", "--port=8080", "--threads=8", "--max-request-body-size=15728640", "server:app"]
