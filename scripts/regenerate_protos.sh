#!/usr/bin/env bash
# Regenerate compiled protobuf modules and mypy stubs from the .proto sources.
#
# Requires:
#   pip install grpcio-tools mypy-protobuf
# Or, on NixOS:
#   nix-shell -p protobuf --run "PATH=\$PWD/.venv/bin:\$PATH ./scripts/regenerate_protos.sh"
set -euo pipefail

PROTO_DIR="custom_components/arctic_spa/pyarcticspa/proto"
# Pin the gencode version we stamp into the generated files. Must be <= the
# protobuf runtime in Home Assistant core (verified against HA OS shipping
# protobuf 6.32.0 in May 2026). Any modern protoc will produce identical
# wire-format messages; only the version validator at module load time
# cares about this number.
GENCODE_PATCH=0

cd "$(git rev-parse --show-toplevel)"

protoc \
  --proto_path="$PROTO_DIR" \
  --python_out="$PROTO_DIR" \
  --mypy_out="$PROTO_DIR" \
  "$PROTO_DIR"/*.proto

# Stamp gencode patch version to the pinned value so HA's runtime check
# (which requires runtime >= gencode) does not reject our modules.
python - <<PY
import re
from pathlib import Path

for path in Path("$PROTO_DIR").glob("*_pb2.py"):
    s = path.read_text()
    s2 = re.sub(
        r"(_runtime_version\.ValidateProtobufRuntimeVersion\([^)]*?Domain\.PUBLIC,\s*\n\s*6,\s*\n\s*32,\s*\n\s*)\d+,",
        r"\g<1>$GENCODE_PATCH,",
        s,
    )
    if s != s2:
        path.write_text(s2)
PY

py_count=$(ls "$PROTO_DIR"/*_pb2.py | wc -l)
pyi_count=$(ls "$PROTO_DIR"/*_pb2.pyi 2>/dev/null | wc -l)
echo "Regenerated $py_count .py modules and $pyi_count .pyi stubs (gencode 6.32.$GENCODE_PATCH)."
