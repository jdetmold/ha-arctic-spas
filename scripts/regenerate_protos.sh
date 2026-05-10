#!/usr/bin/env bash
# Regenerate compiled protobuf modules from the .proto source files.
#
# Requires: pip install grpcio-tools  (provides a vendored protoc)
set -euo pipefail

PROTO_DIR="custom_components/arctic_spa/pyarcticspa/proto"

cd "$(git rev-parse --show-toplevel)"

python -m grpc_tools.protoc \
  --proto_path="$PROTO_DIR" \
  --python_out="$PROTO_DIR" \
  "$PROTO_DIR"/*.proto

echo "Regenerated $(ls "$PROTO_DIR"/*_pb2.py | wc -l) protobuf modules."
