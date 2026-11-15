#!/bin/bash

play_sh_dir() {
    dirname "$(readlink -f "$0")"
}

play_sh_need() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "python3 missing" >&2
        exit 1
    fi
}

play_sh_run() {
    cd "$(play_sh_dir)" || exit 1
    play_sh_need
    PYTHONDONTWRITEBYTECODE=1 python3 src/main.py "$@"
}

play_sh_spawn() {
    local title
    title="$(basename "$(play_sh_dir)")"
    xfce4-terminal \
        --title="$title" \
        -e "bash -c '$0 $*; exec bash'"
}

main() {
    play_sh_run "$@"
}

if [ -t 0 ]; then
    main "$@"
else
    play_sh_spawn "$@"
fi