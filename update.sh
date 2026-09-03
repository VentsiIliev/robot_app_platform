#!/usr/bin/env bash
  set -euo pipefail

  REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  cd "$REPO_DIR"

  if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "Update stopped: commit or stash tracked changes first."
      git status --short
      exit 1
  fi

  echo "Switching to PLP machine configuration branch..."
  git switch plp-machine-config

  echo "Fetching remote updates..."
  git fetch origin

  echo "Merging fair-2026 into plp-machine-config..."
  git merge --no-edit origin/fair-2026

  echo
  echo "Platform update completed."
  echo "Test the platform, then publish the merge with: git push"
