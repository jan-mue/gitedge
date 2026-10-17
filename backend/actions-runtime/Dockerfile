# syntax=docker/dockerfile:1
FROM golang:1.25-bookworm AS engine
RUN --mount=type=bind,source=.,target=/src,readonly \
    --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export SSL_CERT_FILE=/run/proxy-ca.pem GIT_SSL_CAINFO=/run/proxy-ca.pem; fi; \
    apt-get update && apt-get install -y --no-install-recommends patch && \
    cd /src && \
    GOPROXY=direct go mod download github.com/nektos/act github.com/cloudflare/circl github.com/klauspost/compress && \
    go mod download && \
    cp -a /go/pkg/mod/github.com/nektos/act@v0.2.89 /tmp/act && \
    chmod u+w /tmp/act/pkg/artifacts/artifacts_v4.go && \
    patch -d /tmp/act -p1 < artifact-v7.patch && \
    cp go.mod /tmp/gitedge.mod && cp go.sum /tmp/gitedge.sum && \
    go mod edit -modfile=/tmp/gitedge.mod -replace=github.com/nektos/act=/tmp/act && \
    CGO_ENABLED=0 go build -modfile=/tmp/gitedge.mod -mod=readonly -ldflags="-s -w" -trimpath -o /gitedge-exec . && \
    rm -rf /tmp/act /tmp/gitedge.mod /tmp/gitedge.sum

FROM node:24-bookworm-slim
COPY prepare.py prepare-tools.sh actions.txt launch.sh artifact-compat.cjs /build/
RUN --mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem \
    if [ -f /run/proxy-ca.pem ]; then export SSL_CERT_FILE=/run/proxy-ca.pem GIT_SSL_CAINFO=/run/proxy-ca.pem CURL_CA_BUNDLE=/run/proxy-ca.pem PIP_CERT=/run/proxy-ca.pem; fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates curl gpg jq zstd unzip sudo rsync python3-pip python3-venv python3-yaml libicu72 && \
    python3 /build/prepare.py && bash /build/prepare-tools.sh && \
    install -m 755 /build/launch.sh /usr/local/bin/gitedge-launch && \
    install -m 644 /build/artifact-compat.cjs /opt/gitedge/artifact-compat.cjs && \
    mkdir -p /gitedge /opt/hostedtoolcache && \
    rm -rf /var/lib/apt/lists/* /root/.cache /build
COPY --from=engine /gitedge-exec /usr/local/bin/gitedge-exec
ENV AGENT_TOOLSDIRECTORY=/opt/hostedtoolcache RUNNER_TOOL_CACHE=/opt/hostedtoolcache
ENV NODE_OPTIONS="--require=/opt/gitedge/artifact-compat.cjs"
WORKDIR /gitedge
