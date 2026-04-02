#!/usr/bin/env bash
set -euo pipefail

TAG="$1"
VALUES_FILE="$2"

sed -i "s|tag: .*  # api|tag: \"${TAG}\"  # api|" "$VALUES_FILE"
sed -i "s|tag: .*  # portal|tag: \"${TAG}\"  # portal|" "$VALUES_FILE"
sed -i "s|tag: .*  # operator|tag: \"${TAG}\"  # operator|" "$VALUES_FILE"
