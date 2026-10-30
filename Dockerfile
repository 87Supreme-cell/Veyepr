FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8000
ENTRYPOINT ["ai-observability-demo"]
CMD ["--backend", "simulated", "--interval-seconds", "1", "--port", "8000"]

