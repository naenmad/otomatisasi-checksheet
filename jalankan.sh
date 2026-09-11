#!/usr/bin/env bash
# Jalankan Otomatisasi Checksheet FactoryHub (Forward ke run.sh)
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/run.sh" "$@"
