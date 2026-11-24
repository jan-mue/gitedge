# syntax=docker/dockerfile:1
FROM oven/bun:1.4.4@sha256:1d22548f177f4ff38e0c15baa3c2c46c6c2060ba2d1bc573bb4720b407548f1d AS runner-build
WORKDIR /build
COPY package.json bun.lock ./
COPY frontend/package.json frontend/package.json
COPY packages/react-email/package.json packages/react-email/package.json
COPY packages/actions-runner packages/actions-runner
COPY packages/actions-compiler/package.json packages/actions-compiler/package.json
RUN bun install --frozen-lockfile --ignore-scripts --production --filter @gitedge/actions-runner && bun run --filter @gitedge/actions-runner build

FROM node:24-bookworm-slim@sha256:190bcf5115694c9d3c4d654a1aa88177d77600a06d67972fd7bf4cf224f7692c
COPY --from=runner-build /usr/local/bin/bun /usr/local/bin/bun
COPY --from=runner-build --chmod=755 /build/packages/actions-runner/dist/gitedge-launch* /usr/local/bin/
COPY --from=runner-build /build/packages/actions-runner/dist/prepare.mjs /build/prepare.mjs
COPY packages/actions-runner/actions.txt /build/
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export SSL_CERT_FILE=/run/proxy-ca.pem GIT_SSL_CAINFO=/run/proxy-ca.pem CURL_CA_BUNDLE=/run/proxy-ca.pem UV_NATIVE_TLS=true NODE_EXTRA_CA_CERTS=/run/proxy-ca.pem; cp /run/proxy-ca.pem /usr/local/share/ca-certificates/session-proxy.crt; fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates curl gpg jq zstd unzip sudo rsync python3-pip python3-venv libicu72 && \
    update-ca-certificates && bun /build/prepare.mjs && \
    rm -rf /var/lib/apt/lists/* /root/.cache
ENV AGENT_TOOLSDIRECTORY=/opt/hostedtoolcache RUNNER_TOOL_CACHE=/opt/hostedtoolcache
WORKDIR /gitedge
