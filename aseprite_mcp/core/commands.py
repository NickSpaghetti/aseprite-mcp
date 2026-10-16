import asyncio
import atexit
import os

import dotenv

from .worker import AsepriteWorker

_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
dotenv.load_dotenv(dotenv_path=_ENV_PATH)


def _parse_timeout(raw: str) -> float:
    try:
        seconds = float(raw)
    except ValueError:
        raise ValueError(f"ASEPRITE_TIMEOUT must be a number of seconds, got {raw!r}") from None
    if seconds <= 0:
        raise ValueError(f"ASEPRITE_TIMEOUT must be > 0, got {raw!r}")
    return seconds


ASEPRITE_PATH = os.getenv("ASEPRITE_PATH", "aseprite")
# Upper bound on one request. A script that loops forever gets the worker
# killed instead of hanging the tool call.
TIMEOUT_SECONDS = _parse_timeout(os.getenv("ASEPRITE_TIMEOUT", "120"))

worker = AsepriteWorker(ASEPRITE_PATH, TIMEOUT_SECONDS)
atexit.register(worker.close)


async def call(op: str, filename: str | None = None, /, **args):
    """Run the op registered as `op` (see lua/lib.lua) on `filename` and return its result.

    `op` and `filename` are positional-only, so any keyword, including one
    named `filename`, is an op argument. `args` are sent to Lua as JSON; None
    values are left out, so the op sees them as nil. Raises AsepriteError,
    carrying the op's failure code, when the op fails.
    """
    return await asyncio.to_thread(worker.run_op, op, args, filename)


async def run_script(script: str, filename: str | None = None) -> str:
    """Run arbitrary Lua in the worker, with `filename` open as app.activeSprite.

    For run_lua_script; tools call named ops through call(). Returns what the
    chunk printed. A Lua error raises AsepriteError. The sprite is closed
    afterwards, so a chunk that changes it must save it.
    """
    return await asyncio.to_thread(worker.run_script, script, filename)
