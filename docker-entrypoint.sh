#!/bin/sh
set -e

if [ "$1" = "nginx" -o "$1" = "nginx-debug" ]; then
    if [ -d /docker-entrypoint.d ]; then
        for f in /docker-entrypoint.d/*; do
            case "$f" in
                *.sh)
                    if [ -x "$f" ]; then
                        echo "$0: Launching $f";
                        "$f"
                    fi
                    ;;
            esac
        done
    fi
fi

exec "$@"