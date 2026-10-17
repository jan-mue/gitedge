#!/bin/bash
# Toolchain installation happens once during image/snapshot preparation.
set -euo pipefail
python3 -m pip install --break-system-packages 'uv==0.13.0'
uv python install 3.14.0 --install-dir /opt/gitedge/python
uv venv /opt/hostedtoolcache/Python/3.14.0/x64 --python /opt/gitedge/python/cpython-3.14.0-linux-x86_64-gnu/bin/python3.14 --seed
uv pip install --python /opt/hostedtoolcache/Python/3.14.0/x64/bin/python 'pre-commit==4.5.1' 'codecov-cli==11.3.1' 'coverage==7.16.2'
touch /opt/hostedtoolcache/Python/3.14.0/x64.complete
node_version="$(node --version | cut -c2-)"
mkdir -p "/opt/hostedtoolcache/node/$node_version" /opt/hostedtoolcache/uv/0.13.0/x86_64 /root/.bun/bin
ln -s /usr/local "/opt/hostedtoolcache/node/$node_version/x64"
touch "/opt/hostedtoolcache/node/$node_version/x64.complete" /opt/hostedtoolcache/uv/0.13.0/x86_64.complete
ln -s /usr/local/bin/uv /opt/hostedtoolcache/uv/0.13.0/x86_64/uv
ln -s /usr/local/bin/uvx /opt/hostedtoolcache/uv/0.13.0/x86_64/uvx
curl --fail --location --silent --show-error https://github.com/oven-sh/bun/releases/download/bun-v1.4.3/bun-linux-x64.zip -o /tmp/bun.zip
unzip -p /tmp/bun.zip bun-linux-x64/bun >/root/.bun/bin/bun
chmod +x /root/.bun/bin/bun
rm /tmp/bun.zip
