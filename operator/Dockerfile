FROM python:3.12-slim AS base

RUN groupadd --gid 1001 operator && \
    useradd --uid 1001 --gid 1001 --no-create-home --shell /bin/false operator

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir kopf kubernetes pydantic

COPY . .

USER 1001

ENTRYPOINT ["kopf", "run", "--standalone", "--all-namespaces", "/app/main.py"]
