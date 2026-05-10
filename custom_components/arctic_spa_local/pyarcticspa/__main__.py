"""Live packet dump tool: python -m pyarcticspa <ip>."""

from __future__ import annotations

import asyncio
import logging
import sys

from .client import SpaClient
from .models import SpaConfiguration, SpaInfo, SpaState


async def _run(host: str) -> None:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

    def on_state(state: SpaState) -> None:
        print(f"STATE: {state}")  # noqa: T201

    def on_info(info: SpaInfo) -> None:
        print(f"INFO:  {info}")  # noqa: T201

    def on_config(config: SpaConfiguration) -> None:
        print(f"CFG:   {config}")  # noqa: T201

    client = SpaClient(host)
    client.on_state = on_state
    client.on_info = on_info
    client.on_config = on_config
    await client.start()
    try:
        await asyncio.Event().wait()
    finally:
        await client.stop()


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m pyarcticspa <spa-ip>", file=sys.stderr)  # noqa: T201
        sys.exit(2)
    asyncio.run(_run(sys.argv[1]))


if __name__ == "__main__":
    main()
