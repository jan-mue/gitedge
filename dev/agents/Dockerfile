# syntax=docker/dockerfile:1
FROM python:3.14.0-slim-bookworm
ARG AGENT_SANDBOX_REVISION=993fd4aa9f576b8374b8810ef45e7305ed2dd95d
ADD --checksum=sha256:62f6bbac801fe9529618a06a83e4a613ba77eb66236dc871dc1fef38f4e9a531 https://raw.githubusercontent.com/kubernetes-sigs/agent-sandbox/${AGENT_SANDBOX_REVISION}/examples/python-runtime-sandbox/main.py /runtime/main.py
ADD --checksum=sha256:c7641846858c273dbba8e7eacd8ffaed9c5c08f0e2ddceec5550f901c3f50bfc https://raw.githubusercontent.com/kubernetes-sigs/agent-sandbox/${AGENT_SANDBOX_REVISION}/examples/python-runtime-sandbox/requirements.txt /runtime/requirements.txt
RUN --mount=type=secret,id=proxy_ca,required=false \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    apt-get update && apt-get install -y --no-install-recommends bash git util-linux coreutils tar ca-certificates \
    && pip install --no-cache-dir --require-hashes -r /runtime/requirements.txt \
    && rm -rf /var/lib/apt/lists/*
ENV SANDBOX_BASE_DIR=/
WORKDIR /runtime
EXPOSE 8888
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]
