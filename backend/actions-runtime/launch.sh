#!/bin/bash
set -eu
umask 077
export TAR_OPTIONS="--no-same-owner"
exec >/gitedge/log.jsonl 2>&1
trap 'code=$?; printf "%s" "$code" > /gitedge/exit-code' EXIT
mkdir -p /gitedge/source /gitedge/state/cache /gitedge/state/artifacts
printf '%s' "$GITEDGE_JOB" >/gitedge/input.json
unset GITEDGE_JOB
if [ -n "${GITEDGE_RESTORE_URL:-}" ]; then
	curl --fail --silent --show-error "$GITEDGE_RESTORE_URL" | tar -xz -C /gitedge/state
fi
unset GITEDGE_RESTORE_URL
set +e
node /opt/gitedge/runtime/runner.mjs
code=$?
if ! tar -czf /gitedge/state.tar.gz -C /gitedge/state cache artifacts; then
	code=1
fi
if ! tar -czf /gitedge/cache.tar.gz -C /gitedge/state cache; then
	code=1
fi
printf '%s' "$code" >/gitedge/exit-code
complete_url="$(jq -r '.complete_url // empty' /gitedge/input.json)"
if [ -n "$complete_url" ]; then
	curl --retry 3 --retry-delay 1 --retry-max-time 10 --max-time 10 --fail --silent --show-error --request POST "$complete_url" || true
fi
exit "$code"
