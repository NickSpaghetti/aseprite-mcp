import asyncio
import atexit
import os
import subprocess

import dotenv

from .errors import AsepriteError
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


def lua_escape(s: str) -> str:
    """Escape a string for safe embedding inside a Lua double-quoted string literal."""
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\n", "\\n")
         .replace("\r", "\\r")
         .replace("\0", "\\0")
    )


def _failure_text(done: subprocess.CompletedProcess) -> str:
    # Aseprite reports some failures on stdout rather than stderr, so fall back
    # to stdout before giving up.
    text = (done.stderr or "").strip() or (done.stdout or "").strip()
    return text or f"Aseprite exited with code {done.returncode} and printed nothing"


async def run_cli(args: list[str]) -> str:
    """Run a separate Aseprite with command-line arguments and return its stdout.

    For CLI-only features (--save-as, --sheet). Runs in turn with the worker's
    requests. Raises AsepriteError when Aseprite exits non-zero or times out.
    """
    done = await asyncio.to_thread(worker.run_cli, args)
    if done.returncode != 0:
        raise AsepriteError(_failure_text(done))
    return done.stdout


async def call(op: str, filename: str | None = None, /, **args):
    """Run the op registered as `op` (see lua/lib.lua) on `filename` and return its result.

    `op` and `filename` are positional-only, so any keyword, including one
    named `filename`, is an op argument. `args` are sent to Lua as JSON; None
    values are left out, so the op sees them as nil. Raises AsepriteError, carrying the op's failure code, when the
    op fails.
    """
    return await asyncio.to_thread(worker.run_op, op, args, filename)


async def run_script(script: str, filename: str | None = None, check_errors: bool = True) -> str:
    """Run a Lua chunk in the worker, with `filename` open as app.activeSprite.

    Returns what the chunk printed. The sprite is closed afterwards, so a chunk
    that changes it must save it. Curated scripts signal failure by printing a
    line starting with "ERROR:"; with check_errors the first one is raised as
    AsepriteError. Pass check_errors=False for user scripts.
    """
    output = await asyncio.to_thread(worker.run_script, script, filename)
    if check_errors:
        for line in output.splitlines():
            if line.startswith("ERROR:"):
                raise AsepriteError(line[len("ERROR:"):])
    return output
