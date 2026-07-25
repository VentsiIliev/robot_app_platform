#!/usr/bin/env bash

set -u

usage() {
    cat <<'EOF'
Usage:
  scripts/profile_pid.sh [PID] [duration_s] [output_dir]

Examples:
  scripts/profile_pid.sh
  scripts/profile_pid.sh 22404
  scripts/profile_pid.sh 22404 20
  scripts/profile_pid.sh 22404 30 /tmp/robot_profile

What it collects:
  - process metadata
  - per-thread ps snapshot
  - top thread snapshots
  - pidstat per-thread samples (if available)
  - py-spy top + flamegraph (if available)
  - strace summary (if available and attach is permitted)
  - perf sample (if available and permitted)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 1
fi

detect_robot_pid() {
    local matches
    mapfile -t matches < <(pgrep -af "python.*src/bootstrap/main.py" || true)
    if [[ "${#matches[@]}" -eq 0 ]]; then
        return 1
    fi
    if [[ "${#matches[@]}" -gt 1 ]]; then
        printf 'error: multiple robot platform processes found\n' >&2
        printf '%s\n' "${matches[@]}" >&2
        return 2
    fi
    printf '%s\n' "${matches[0]%% *}"
}

is_positive_int() {
    [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -gt 0 ]]
}

PID=""
DURATION_S="15"
OUT_DIR=""

if [[ $# -ge 1 ]]; then
    if is_positive_int "$1" && [[ -d "/proc/$1" ]]; then
        PID="$1"
        DURATION_S="${2:-15}"
        OUT_DIR="${3:-}"
    elif is_positive_int "$1"; then
        PID="$(detect_robot_pid)" || exit $?
        DURATION_S="$1"
        OUT_DIR="${2:-}"
    else
        echo "error: first argument must be a running PID or duration_s" >&2
        usage
        exit 1
    fi
else
    PID="$(detect_robot_pid)" || exit $?
fi

if [[ ! -d "/proc/$PID" ]]; then
    echo "error: PID $PID is not running" >&2
    exit 1
fi

if ! is_positive_int "$DURATION_S"; then
    echo "error: duration_s must be a positive integer" >&2
    exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_DIR:-./scripts/profile_${PID}_${STAMP}}"

mkdir -p "$OUT_DIR"

log() {
    printf '[profile] %s\n' "$*"
}

fix_bundle_ownership() {
    local owner_user="${SUDO_USER:-}"
    if [[ -z "$owner_user" ]]; then
        return 0
    fi
    if ! id "$owner_user" >/dev/null 2>&1; then
        log "skipping ownership fix: unknown sudo user '$owner_user'"
        return 0
    fi
    if chown -R "$owner_user:$owner_user" "$OUT_DIR" >/dev/null 2>&1; then
        log "restored bundle ownership to $owner_user"
    else
        log "warning: failed to restore bundle ownership to $owner_user"
    fi
}

run_capture() {
    local name="$1"
    shift
    local out_file="$OUT_DIR/$name.txt"
    log "collecting $name"
    {
        printf '$ %s\n\n' "$*"
        "$@"
    } >"$out_file" 2>&1
}

run_timed_capture() {
    local name="$1"
    shift
    local out_file="$OUT_DIR/$name.txt"
    log "collecting $name for ${DURATION_S}s"
    {
        printf '$ %s\n\n' "$*"
        "$@"
    } >"$out_file" 2>&1
}

find_py_spy() {
    if command -v py-spy >/dev/null 2>&1; then
        command -v py-spy
        return 0
    fi
    if [[ -x "./.venv/bin/py-spy" ]]; then
        printf '%s\n' "./.venv/bin/py-spy"
        return 0
    fi
    return 1
}

log "writing profile bundle to $OUT_DIR"

run_capture meta bash -lc "date; uname -a; pwd"
run_capture process ps -p "$PID" -o pid,ppid,user,etime,%cpu,%mem,stat,comm,args
run_capture threads ps -T -p "$PID" -o pid,tid,pcpu,pmem,time,stat,wchan:32,comm --sort=-pcpu
run_capture cmdline bash -lc "tr '\0' ' ' </proc/$PID/cmdline; echo"
run_capture limits cat "/proc/$PID/limits"
run_capture status cat "/proc/$PID/status"

run_timed_capture top_threads top -b -H -d 1 -n "$DURATION_S" -p "$PID"

if command -v pidstat >/dev/null 2>&1; then
    run_timed_capture pidstat_threads pidstat -t -p "$PID" 1 "$DURATION_S"
else
    log "skipping pidstat_threads: pidstat not installed"
fi

if PYSPY_BIN="$(find_py_spy)"; then
    log "collecting pyspy_top for ${DURATION_S}s"
    timeout "$DURATION_S" "$PYSPY_BIN" top --pid "$PID" --delay 1 \
        >"$OUT_DIR/pyspy_top.txt" 2>&1 || true
    log "collecting pyspy_flamegraph for ${DURATION_S}s"
    "$PYSPY_BIN" record -o "$OUT_DIR/pyspy_flamegraph.svg" --pid "$PID" --duration "$DURATION_S" \
        >"$OUT_DIR/pyspy_flamegraph.txt" 2>&1 || true
else
    log "skipping py-spy: not installed"
fi

if command -v strace >/dev/null 2>&1; then
    log "collecting strace_summary for ${DURATION_S}s"
    timeout "$DURATION_S" strace -c -f -p "$PID" \
        >"$OUT_DIR/strace_summary.txt" 2>&1 || true
else
    log "skipping strace_summary: strace not installed"
fi

if command -v perf >/dev/null 2>&1; then
    log "collecting perf sample for ${DURATION_S}s"
    perf record -g -p "$PID" -o "$OUT_DIR/perf.data" -- sleep "$DURATION_S" \
        >"$OUT_DIR/perf_record.txt" 2>&1 || true
    if [[ -s "$OUT_DIR/perf.data" ]]; then
        perf report --stdio -i "$OUT_DIR/perf.data" \
            >"$OUT_DIR/perf_report.txt" 2>&1 || true
    fi
else
    log "skipping perf: perf not installed"
fi

cat >"$OUT_DIR/README.txt" <<EOF
Profile bundle for PID $PID
Created: $(date)
Duration: ${DURATION_S}s

Important files:
  - process.txt
  - threads.txt
  - top_threads.txt
  - pidstat_threads.txt            (if pidstat was available)
  - pyspy_top.txt                  (if py-spy was available)
  - pyspy_flamegraph.svg           (if py-spy was available)
  - strace_summary.txt             (if strace attach succeeded)
  - perf_report.txt                (if perf attach succeeded)

Notes:
  - strace/perf may fail without sufficient permissions.
  - py-spy may show limited detail if the hot work is inside native OpenCV code.
  - top/ps percentages and py-spy/perf samples should be interpreted together.
EOF

fix_bundle_ownership

log "done"
log "bundle: $OUT_DIR"
