#!/bin/bash
set -eu
umask 077
export TAR_OPTIONS="--no-same-owner"
exec >/gitedge/log.jsonl 2>&1
finish() {
	code=$?
	trap - EXIT
	set +e
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
}
trap finish EXIT
trap 'exit 124' TERM
trap 'exit 130' INT
mkdir -p /gitedge/source /gitedge/state/cache /gitedge/state/artifacts
printf '%s' "$GITEDGE_JOB" >/gitedge/input.json
unset GITEDGE_JOB
timeout_seconds="$(jq -r '.timeout_seconds' /gitedge/input.json)"
if [ -n "${GITEDGE_RESTORE_URL:-}" ]; then
	curl --fail --silent --show-error "$GITEDGE_RESTORE_URL" | tar -xz -C /gitedge/state
fi
unset GITEDGE_RESTORE_URL
# Keep the shell alive to archive state and notify the controller after a timeout.
timeout --signal=TERM --kill-after=5 "$timeout_seconds" node /opt/gitedge/runtime/runner.mjs
