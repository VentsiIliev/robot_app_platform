#!/usr/bin/env bash

set -u

usage() {
    cat <<'EOF'
Usage:
  scripts/profile_paint_vision_isolated.sh [profile_duration_s] [warmup_s] [runner_duration_s] [output_dir] [-- runner_args...]

Examples:
  scripts/profile_paint_vision_isolated.sh
  scripts/profile_paint_vision_isolated.sh 20
  scripts/profile_paint_vision_isolated.sh 20 20
  scripts/profile_paint_vision_isolated.sh 20 20 135
  scripts/profile_paint_vision_isolated.sh 20 20 135 /tmp/paint_vision_profile
  scripts/profile_paint_vision_isolated.sh 20 -- --snapshot-interval 2

Behavior:
  - starts scripts/run_paint_vision_isolated.py in the background
  - waits for a warm-up period before collecting profiles
  - profiles that exact PID using scripts/profile_pid.sh
  - stores the runner stdout/stderr beside the normal profile bundle
  - stops the isolated runner automatically afterward
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 1
fi

is_positive_int() {
    [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -gt 0 ]]
}

PROFILE_DURATION_S="15"
WARMUP_S="20"
RUNNER_DURATION_S=""
OUT_DIR=""
RUNNER_ARGS=()

POSITIONAL=()
AFTER_DASHDASH=0
for arg in "$@"; do
    if [[ "$AFTER_DASHDASH" -eq 1 ]]; then
        RUNNER_ARGS+=("$arg")
        continue
    fi
    if [[ "$arg" == "--" ]]; then
        AFTER_DASHDASH=1
        continue
    fi
    POSITIONAL+=("$arg")
done

if [[ "${#POSITIONAL[@]}" -ge 1 ]]; then
    PROFILE_DURATION_S="${POSITIONAL[0]}"
fi
if [[ "${#POSITIONAL[@]}" -ge 2 ]]; then
    WARMUP_S="${POSITIONAL[1]}"
fi
if [[ "${#POSITIONAL[@]}" -ge 3 ]]; then
    RUNNER_DURATION_S="${POSITIONAL[2]}"
fi
if [[ "${#POSITIONAL[@]}" -ge 4 ]]; then
    OUT_DIR="${POSITIONAL[3]}"
fi
if [[ "${#POSITIONAL[@]}" -gt 4 ]]; then
    echo "error: too many positional arguments" >&2
    usage
    exit 1
fi

if ! is_positive_int "$PROFILE_DURATION_S"; then
    echo "error: profile_duration_s must be a positive integer" >&2
    exit 1
fi

if ! is_positive_int "$WARMUP_S"; then
    echo "error: warmup_s must be a positive integer" >&2
    exit 1
fi

if [[ -z "$RUNNER_DURATION_S" ]]; then
    RUNNER_DURATION_S="$((WARMUP_S + PROFILE_DURATION_S * 5 + 15))"
fi

if ! is_positive_int "$RUNNER_DURATION_S"; then
    echo "error: runner_duration_s must be a positive integer" >&2
    exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_DIR:-./scripts/paint_vision_isolated_profile_${STAMP}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_SCRIPT="$SCRIPT_DIR/run_paint_vision_isolated.py"
PID_PROFILER="$SCRIPT_DIR/profile_pid.sh"

mkdir -p "$OUT_DIR"

log() {
    printf '[paint-vision-profile] %s\n' "$*"
}

RUNNER_PID=""

cleanup() {
    if [[ -n "$RUNNER_PID" ]] && kill -0 "$RUNNER_PID" >/dev/null 2>&1; then
        log "stopping isolated runner PID $RUNNER_PID"
        kill -TERM "$RUNNER_PID" >/dev/null 2>&1 || true
        wait "$RUNNER_PID" >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT INT TERM

RUNNER_CMD=(python3 "$RUNNER_SCRIPT" --duration "$RUNNER_DURATION_S")
if [[ "${#RUNNER_ARGS[@]}" -gt 0 ]]; then
    RUNNER_CMD+=("${RUNNER_ARGS[@]}")
fi

log "starting isolated paint vision runner"
{
    printf '$'
    for token in "${RUNNER_CMD[@]}"; do
        printf ' %q' "$token"
    done
    printf '\n\n'
} >"$OUT_DIR/vision_runner.txt"

"${RUNNER_CMD[@]}" >>"$OUT_DIR/vision_runner.txt" 2>&1 &
RUNNER_PID=$!
log "runner PID: $RUNNER_PID"

sleep 2
if ! kill -0 "$RUNNER_PID" >/dev/null 2>&1; then
    echo "error: isolated vision runner exited before profiling started" >&2
    exit 1
fi

log "warming up isolated runner for ${WARMUP_S}s"
sleep "$WARMUP_S"
if ! kill -0 "$RUNNER_PID" >/dev/null 2>&1; then
    echo "error: isolated vision runner exited during warm-up" >&2
    exit 1
fi

log "profiling isolated runner for ${PROFILE_DURATION_S}s"
if [[ "$EUID" -eq 0 ]]; then
    "$PID_PROFILER" "$RUNNER_PID" "$PROFILE_DURATION_S" "$OUT_DIR"
else
    sudo "$PID_PROFILER" "$RUNNER_PID" "$PROFILE_DURATION_S" "$OUT_DIR"
fi

log "profile bundle: $OUT_DIR"
