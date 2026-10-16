import os
import subprocess
import tempfile

import dotenv

from .errors import AsepriteError

_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
dotenv.load_dotenv(dotenv_path=_ENV_PATH)

ASEPRITE_PATH = os.getenv("ASEPRITE_PATH", "aseprite")


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
    # Aseprite reports some failures, Lua syntax errors among them, on stdout
    # rather than stderr, so fall back to stdout before giving up.
    text = (done.stderr or "").strip() or (done.stdout or "").strip()
    return text or f"Aseprite exited with code {done.returncode} and printed nothing"


async def run_cli(args: list[str]) -> str:
    """Run Aseprite with command-line arguments and return its stdout.

    Raises AsepriteError when Aseprite exits non-zero.
    """
    done = subprocess.run([ASEPRITE_PATH, *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise AsepriteError(_failure_text(done))
    return done.stdout


async def run_script(script: str, filename: str | None = None, check_errors: bool = True) -> str:
    """Run a Lua script in batch mode, with `filename` opened first, and return stdout.

    Batch-mode scripts cannot set the process exit code, so curated scripts
    signal failure by printing a line starting with "ERROR:". With
    check_errors, the first such line is raised as AsepriteError. Pass
    check_errors=False for user scripts, whose output is returned untouched.
    """
    with tempfile.NamedTemporaryFile(suffix=".lua", delete=False, mode="w") as tmp:
        tmp.write(script)
        script_path = tmp.name
    try:
        args = ["--batch"] + ([filename] if filename else []) + ["--script", script_path]
        output = await run_cli(args)
    finally:
        os.remove(script_path)

    if check_errors:
        for line in output.splitlines():
            if line.startswith("ERROR:"):
                raise AsepriteError(line[len("ERROR:"):])
    return output
