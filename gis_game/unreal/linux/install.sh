#!/usr/bin/env bash
# User-local installer for the packaged Goat Island Skiff Linux game.
set -euo pipefail

if [[ ${1:-} == --help ]]; then
    printf 'Usage: ./install.sh\nInstalls Goat Island Skiff for the current Linux user. No sudo required.\n'
    exit 0
fi
if (( $# != 0 )); then
    printf 'Unknown option. Run ./install.sh --help for usage.\n' >&2
    exit 2
fi
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
    printf 'This download needs a 64-bit x86 Linux computer.\n' >&2
    exit 1
fi

package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ ! -f "$package_dir/GISGame.sh" || ! -d "$package_dir/GISGame/Content/Paks" ]]; then
    printf 'The packaged game is incomplete. Extract the entire download before installing.\n' >&2
    exit 1
fi
if [[ ! -f "$package_dir/release-id.txt" ]]; then
    printf 'The release ID is missing from this package.\n' >&2
    exit 1
fi
IFS= read -r release_id < "$package_dir/release-id.txt"
if [[ ! $release_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
    printf 'The release ID is invalid.\n' >&2
    exit 1
fi

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
if [[ $data_home != /* ]]; then
    printf 'XDG_DATA_HOME must be an absolute path.\n' >&2
    exit 1
fi
install_root="$data_home/goat-island-skiff"
builds_dir="$install_root/builds"
build_dir="$builds_dir/$release_id"
bin_dir="$HOME/.local/bin"
launcher="$bin_dir/goat-island-skiff"
desktop_dir="$data_home/applications"
desktop_file="$desktop_dir/goat-island-skiff.desktop"

if [[ -e $launcher ]] && ! grep -q '^# GISGame managed launcher$' "$launcher"; then
    printf 'A different file already exists at %s; installation stopped.\n' "$launcher" >&2
    exit 1
fi
if [[ -e $desktop_file ]] && ! grep -q '^X-GISGame-Managed=true$' "$desktop_file"; then
    printf 'A different app shortcut already exists at %s; installation stopped.\n' "$desktop_file" >&2
    exit 1
fi
if [[ -e "$install_root/current" && ! -L "$install_root/current" ]]; then
    printf 'An unexpected file exists at %s/current; installation stopped.\n' "$install_root" >&2
    exit 1
fi

mkdir -p -- "$builds_dir" "$bin_dir" "$desktop_dir"
if [[ ! -d "$build_dir" ]]; then
    incoming="$(mktemp -d "$builds_dir/.incoming.XXXXXXXX")"
    cleanup() {
        if [[ -n ${incoming:-} && -d $incoming && $incoming == "$builds_dir"/.incoming.* ]]; then
            rm -rf -- "$incoming"
        fi
    }
    trap cleanup EXIT
    cp -a -- "$package_dir"/. "$incoming"/
    mv -- "$incoming" "$build_dir"
    incoming=""
    trap - EXIT
elif ! diff -qr -- "$package_dir" "$build_dir" > /dev/null 2>&1; then
    printf 'Release %s is already installed with different files. Ask for a newly versioned download; the existing install was left intact.\n' "$release_id" >&2
    exit 1
fi
if [[ ! -x "$build_dir/GISGame.sh" ]]; then
    printf 'The packaged launcher is not executable. Re-extract the download and try again.\n' >&2
    exit 1
fi

ln -sfn -- "builds/$release_id" "$install_root/current"
{
    printf '#!/usr/bin/env bash\n# GISGame managed launcher\nset -e\n'
    printf 'cd %q\n' "$install_root/current"
    printf 'exec %q "$@"\n' "$install_root/current/GISGame.sh"
} > "$launcher"
chmod 755 "$launcher"

# Desktop Exec arguments must be quoted and escaped as specified by freedesktop.
desktop_exec=${launcher//\\/\\\\}
desktop_exec=${desktop_exec//\"/\\\"}
desktop_exec=${desktop_exec//\$/\\\$}
desktop_exec=${desktop_exec//\`/\\\`}
desktop_exec=${desktop_exec//%/%%}
cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=Goat Island Skiff
Comment=Sail Lake Greenwood in a Goat Island Skiff
Exec="$desktop_exec"
Terminal=false
Icon=applications-games
Categories=Game;Simulation;
X-GISGame-Managed=true
EOF

printf 'Installed Goat Island Skiff %s.\n' "$release_id"
printf 'Open it from your app menu, or run: %s\n' "$launcher"
printf 'You can remove the extracted download after confirming the game starts.\n'
