FROM python:3.12-slim

RUN useradd --uid 1001 --no-create-home --shell /bin/false --no-user-group -g 0 apprunner

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir kopf kubernetes pydantic

COPY . .

USER 1001

ENTRYPOINT ["kopf", "run", "--standalone", "--all-namespaces", "/app/main.py"]
