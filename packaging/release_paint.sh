#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
VERSION=""
PUBLISH=false
SKIP_TESTS=false

usage() {
    cat <<'EOF'
Usage: ./packaging/release_paint.sh VERSION [--publish] [--skip-tests]

Prepare a versioned Paint Robot System bundle. By default, the script runs
checks, tests, builds the bundle, and creates a local archive without changing
Git or GitHub.

Arguments:
  VERSION       Semantic version without a leading "v", for example 1.0.0
  --publish     Create and push paint-vVERSION, then create a GitHub release
  --skip-tests  Skip the test suite (intended only when tests already passed)
  -h, --help    Show this help

Examples:
  ./packaging/release_paint.sh 1.0.0
  ./packaging/release_paint.sh 1.0.0 --publish
EOF
}

while (($#)); do
    case "$1" in
        --publish)
            PUBLISH=true
            ;;
        --skip-tests)
            SKIP_TESTS=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            if [[ -n "$VERSION" ]]; then
                echo "Only one version may be supplied." >&2
                usage >&2
                exit 2
            fi
            VERSION="$1"
            ;;
    esac
    shift
done

if [[ -z "$VERSION" ]]; then
    echo "A version is required." >&2
    usage >&2
    exit 2
fi

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
    echo "Invalid semantic version: $VERSION" >&2
    exit 2
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python environment not found: $PYTHON_BIN" >&2
    exit 1
fi

MISSING_TOOLS=()
if ! "$PYTHON_BIN" -c "import PyInstaller" 2>/dev/null; then
    MISSING_TOOLS+=("PyInstaller")
fi
if [[ "$SKIP_TESTS" == false ]] && ! "$PYTHON_BIN" -c "import coverage" 2>/dev/null; then
    MISSING_TOOLS+=("coverage")
fi
if ((${#MISSING_TOOLS[@]})); then
    echo "Missing release tooling: ${MISSING_TOOLS[*]}" >&2
    echo "Install it with:" >&2
    echo "  $PYTHON_BIN -m pip install -r packaging/requirements-build.txt" >&2
    exit 1
fi

cd "$PROJECT_ROOT"

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "work" ]]; then
    echo "Releases must be prepared from the work branch; current branch: $CURRENT_BRANCH" >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "The working tree is not clean. Commit or stash changes before releasing:" >&2
    git status --short >&2
    exit 1
fi

PAINT_VERSION="$(
    "$PYTHON_BIN" -c \
        'import pathlib,re; text=pathlib.Path("src/robot_systems/paint/paint_robot_system.py").read_text(); match=re.search(r"metadata\s*=\s*SystemMetadata\((?:(?!\n\s*\)).)*?version\s*=\s*[\"'\'']([^\"'\'']+)", text, re.S); print(match.group(1) if match else "")'
)"
if [[ "$PAINT_VERSION" != "$VERSION" ]]; then
    echo "Requested version $VERSION does not match PaintSystem metadata version $PAINT_VERSION." >&2
    exit 1
fi

TAG="paint-v$VERSION"
ARCHITECTURE="$(uname -m)"
ARCHIVE_DIR="$PROJECT_ROOT/dist/releases"
ARCHIVE="$ARCHIVE_DIR/paint-robot-$VERSION-linux-$ARCHITECTURE.tar.gz"
CHECKSUM="$ARCHIVE.sha256"

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    echo "Tag already exists locally: $TAG" >&2
    exit 1
fi

if [[ "$SKIP_TESTS" == false ]]; then
    "$PYTHON_BIN" tests/run_tests.py
fi

"$PROJECT_ROOT/packaging/build_paint.sh"

mkdir -p "$ARCHIVE_DIR"
tar -czf "$ARCHIVE" -C "$PROJECT_ROOT/dist" paint-robot
(
    cd "$ARCHIVE_DIR"
    sha256sum "$(basename "$ARCHIVE")" >"$(basename "$CHECKSUM")"
)

echo "Release archive prepared:"
echo "  $ARCHIVE"
echo "  $CHECKSUM"

if [[ "$PUBLISH" == false ]]; then
    echo "Nothing was tagged or published. Test the bundle, then rerun with --publish."
    exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI (gh) is required for --publish." >&2
    exit 1
fi

gh auth status >/dev/null
git fetch origin work --tags

if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/work)" ]]; then
    echo "Local work must exactly match origin/work before publishing." >&2
    exit 1
fi

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    echo "Tag appeared during fetch and will not be overwritten: $TAG" >&2
    exit 1
fi

git tag -a "$TAG" -m "Paint Robot System $VERSION"
git push origin "$TAG"
gh release create "$TAG" \
    "$ARCHIVE" \
    "$CHECKSUM" \
    --title "Paint Robot System $VERSION" \
    --generate-notes \
    --verify-tag

echo "Published Paint Robot System $VERSION as $TAG."
