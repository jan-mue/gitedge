# syntax=docker/dockerfile:1
ARG UBUNTU_IMAGE=ubuntu:24.04

FROM oven/bun:1.4.4 AS runner-build
WORKDIR /build
COPY package.json bun.lock ./
COPY frontend/package.json frontend/package.json
COPY packages/react-email/package.json packages/react-email/package.json
COPY packages/actions-runner packages/actions-runner
COPY packages/actions-compiler/package.json packages/actions-compiler/package.json
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export NODE_EXTRA_CA_CERTS=/run/proxy-ca.pem; fi; \
    bun install --frozen-lockfile --ignore-scripts --production --filter @gitedge/actions-runner && \
    bun run --filter @gitedge/actions-runner build

FROM node:24-bookworm-slim AS node

FROM ${UBUNTU_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=runner-build /usr/local/bin/bun /usr/local/bin/bun
COPY --from=runner-build /build/packages/actions-runner/dist/prepare.mjs /build/prepare.mjs
COPY packages/actions-runner/actions.txt /build/
# Ubuntu repositories supply security updates for each release.
# hadolint ignore=DL3008
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then mkdir -p /usr/local/share/ca-certificates; export SSL_CERT_FILE=/run/proxy-ca.pem GIT_SSL_CAINFO=/run/proxy-ca.pem CURL_CA_BUNDLE=/run/proxy-ca.pem UV_NATIVE_TLS=true NODE_EXTRA_CA_CERTS=/run/proxy-ca.pem; cp /run/proxy-ca.pem /usr/local/share/ca-certificates/session-proxy.crt; fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates curl gpg jq zstd unzip sudo rsync python3-pip python3-venv libicu-dev && \
    update-ca-certificates && \
    ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
    bun /build/prepare.mjs && \
    rm -rf /var/lib/apt/lists/* /root/.cache && \
    rm -f /usr/local/share/ca-certificates/session-proxy.crt && update-ca-certificates
COPY --from=runner-build --chmod=755 /build/packages/actions-runner/dist/gitedge-launch* /usr/local/bin/
ENV AGENT_TOOLSDIRECTORY=/opt/hostedtoolcache RUNNER_TOOL_CACHE=/opt/hostedtoolcache
WORKDIR /gitedge
