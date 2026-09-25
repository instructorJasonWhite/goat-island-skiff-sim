#!/usr/bin/env bash
# Install a real release in a disposable Ubuntu container and launch as a
# non-root player. A GPU is not available here, so Unreal runs with null RHI.
set -euo pipefail

if (( $# != 1 )); then
    printf 'Usage: %s /path/to/Goat-Island-Skiff-Ubuntu.deb\n' "$0" >&2
    exit 2
fi
package="$(readlink -f -- "$1")"
if [[ ! -f $package ]]; then
    printf 'Package not found: %s\n' "$package" >&2
    exit 1
fi

docker run --rm --mount "type=bind,src=$package,dst=/tmp/game.deb,readonly" ubuntu:24.04 bash -euc '
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq /tmp/game.deb passwd >/tmp/install.log 2>&1 || {
        cat /tmp/install.log
        exit 1
    }
    test "$(dpkg-query -W -f="\${Status}" goat-island-skiff)" = "install ok installed"
    test "$(stat -c %u /opt/goat-island-skiff/GISGame/Binaries/Linux/GISGame-Linux-Shipping)" = 0
    test -x /usr/bin/goat-island-skiff
    test -f /usr/share/applications/goat-island-skiff-ubuntu.desktop
    useradd --create-home --shell /bin/sh player
    su -s /bin/sh player -c "test ! -w /opt/goat-island-skiff && test -x /opt/goat-island-skiff/GISGame/Binaries/Linux/GISGame-Linux-Shipping"

    set +e
    su -s /bin/sh player -c "cd /home/player && timeout 15s goat-island-skiff -nullrhi -unattended -nosound -stdout" >/tmp/game.log 2>&1
    result=$?
    set -e
    if [[ $result != 124 ]]; then
        printf "Headless launch exited unexpectedly: %s\n" "$result" >&2
        tail -n 80 /tmp/game.log >&2
        exit 1
    fi
    if grep -Eqi "permission denied|failed to open|fatal error" /tmp/game.log; then
        tail -n 80 /tmp/game.log >&2
        exit 1
    fi
    printf "Ubuntu package installed, launcher started as non-root, and remained running for 15 seconds.\n"
    tail -n 8 /tmp/game.log
'
