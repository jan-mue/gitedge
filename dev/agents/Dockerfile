# syntax=docker/dockerfile:1
FROM python:3.14.10-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash git util-linux coreutils findutils ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /workspace /opt/gitedge
WORKDIR /workspace
CMD ["bash"]
