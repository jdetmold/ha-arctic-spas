#!/usr/bin/env bash
# Regenerate compiled protobuf modules and mypy stubs from the .proto sources.
#
# Requires:
#   pip install grpcio-tools mypy-protobuf
# Or, on NixOS:
#   nix-shell -p protobuf --run "PATH=\$PWD/.venv/bin:\$PATH ./scripts/regenerate_protos.sh"
set -euo pipefail

PROTO_DIR="custom_components/arctic_spa/pyarcticspa/proto"

cd "$(git rev-parse --show-toplevel)"

protoc \
  --proto_path="$PROTO_DIR" \
  --python_out="$PROTO_DIR" \
  --mypy_out="$PROTO_DIR" \
  "$PROTO_DIR"/*.proto

py_count=$(ls "$PROTO_DIR"/*_pb2.py | wc -l)
pyi_count=$(ls "$PROTO_DIR"/*_pb2.pyi 2>/dev/null | wc -l)
echo "Regenerated $py_count .py modules and $pyi_count .pyi stubs."
