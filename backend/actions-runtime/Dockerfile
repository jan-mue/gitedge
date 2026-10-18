# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim
COPY prepare.py prepare-tools.sh actions.txt /build/
COPY package.json package-lock.json /opt/gitedge/runtime/
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export SSL_CERT_FILE=/run/proxy-ca.pem GIT_SSL_CAINFO=/run/proxy-ca.pem CURL_CA_BUNDLE=/run/proxy-ca.pem PIP_CERT=/run/proxy-ca.pem NODE_EXTRA_CA_CERTS=/run/proxy-ca.pem; fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates curl gpg jq zstd unzip sudo rsync python3-pip python3-venv python3-yaml libicu72 && \
    npm ci --prefix /opt/gitedge/runtime --omit=dev --ignore-scripts && \
    python3 /build/prepare.py && bash /build/prepare-tools.sh && \
    mkdir -p /gitedge /opt/hostedtoolcache && \
    rm -rf /var/lib/apt/lists/* /root/.cache /build
COPY expressions.mjs runner.mjs storage.mjs /opt/gitedge/runtime/
COPY --chmod=755 launch.sh /usr/local/bin/gitedge-launch
COPY artifact-compat.cjs /opt/gitedge/artifact-compat.cjs
ENV AGENT_TOOLSDIRECTORY=/opt/hostedtoolcache RUNNER_TOOL_CACHE=/opt/hostedtoolcache
ENV NODE_OPTIONS="--require=/opt/gitedge/artifact-compat.cjs"
WORKDIR /gitedge
