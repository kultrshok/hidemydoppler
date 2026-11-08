#!/usr/bin/env bash
# hidemydoppler - Prepare System (Linux CLI)
# Installs python3 (>=3.9), numpy, scipy and ffmpeg, then runs setup_check.py.
#   ./prepare_linux.sh          # asks before installing
#   ./prepare_linux.sh --yes    # no questions
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YES=0; [[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]] && YES=1
SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
run()  { printf '   $ %s\n' "$*"; "$@"; }

if [[ $YES -eq 0 ]]; then
  read -r -p "Install hidemydoppler prerequisites (python3, numpy, scipy, ffmpeg)? [y/N] " a
  [[ "$a" =~ ^[Yy] ]] || { echo "Cancelled."; exit 1; }
fi

. /etc/os-release 2>/dev/null || true
say "Detected: ${PRETTY_NAME:-unknown Linux}"

if command -v apt-get >/dev/null; then
  run $SUDO apt-get update
  run $SUDO apt-get install -y python3 python3-pip python3-venv python3-numpy python3-scipy ffmpeg
elif command -v dnf >/dev/null; then
  PKGS="python3 python3-pip python3-numpy python3-scipy"
  if [[ "${ID:-}" == "fedora" ]]; then
    REL="$(rpm -E %fedora)"
    run $SUDO dnf install -y \
      "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${REL}.noarch.rpm" || true
  else  # RHEL / Rocky / Alma / CentOS Stream
    REL="$(rpm -E %rhel)"
    run $SUDO dnf install -y epel-release || \
      run $SUDO dnf install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-${REL}.noarch.rpm"
    if [[ "$REL" == "8" ]]; then run $SUDO dnf config-manager --set-enabled powertools || true
    else run $SUDO dnf config-manager --set-enabled crb || true; fi
    run $SUDO dnf install -y \
      "https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-${REL}.noarch.rpm" || true
  fi
  run $SUDO dnf install -y $PKGS ffmpeg
elif command -v pacman >/dev/null; then
  run $SUDO pacman -Sy --noconfirm --needed python python-pip python-numpy python-scipy ffmpeg
elif command -v zypper >/dev/null; then
  run $SUDO zypper --non-interactive install python3 python3-pip python3-numpy python3-scipy ffmpeg
else
  warn "No supported package manager (apt/dnf/pacman/zypper). Install python3, numpy, scipy, ffmpeg by hand."
  exit 1
fi

# Distro Python too old or numpy/scipy missing? fall back to a venv
if ! python3 -c "import sys; assert sys.version_info >= (3,9); import numpy, scipy" 2>/dev/null; then
  warn "System numpy/scipy unusable; creating $HERE/.venv"
  run python3 -m venv "$HERE/.venv"
  run "$HERE/.venv/bin/pip" install --upgrade numpy scipy
  PY="$HERE/.venv/bin/python"
else
  PY="python3"
fi

say "Final check"
"$PY" "$HERE/setup_check.py" --check
say "Done. Start the UI with:  $PY $HERE/ui.py"
