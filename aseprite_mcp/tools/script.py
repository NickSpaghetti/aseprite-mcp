from ..core.commands import run_script
from ..core.boundary import require_file
from ..core.errors import InputError
from .. import mcp


@mcp.tool()
async def run_lua_script(script: str, filename: str = "") -> str:
    """Execute arbitrary Aseprite Lua code (escape hatch).

    Use this when no dedicated tool covers what you need. The full API
    is documented at https://www.aseprite.org/api/. Anything the curated
    tools do can also be done here — they are Lua underneath.

    The script runs in the server's long-lived headless Aseprite:
    - When filename is given, it is opened first and available as
      app.activeSprite.
    - Every sprite is closed when the script ends, and changes are NOT
      saved automatically: call spr:saveAs(spr.filename) if you modified
      the sprite.
    - Nothing carries over to the next call. Globals you set and sprites
      you open are gone, so each call starts from the files on disk.
    - print() is how you return data. A Lua error fails the call with its
      message; a script that runs cleanly can still have done the wrong
      thing, so print what you need to verify.
    - Coordinates on cel images are cel-local: offset sprite-global
      coordinates by cel.position before getPixel/putPixel.
    - A script that runs longer than ASEPRITE_TIMEOUT seconds (default
      120) is killed.

    WARNING: this executes unrestricted code (including io/os access)
    on the host running Aseprite. Only pass scripts you trust.

    Args:
        script: Lua source code to execute
        filename: Optional Aseprite file to open before running
    """
    if not script.strip():
        raise InputError("Script cannot be empty")
    if filename:
        require_file(filename)

    output = await run_script(script, filename or None, check_errors=False)
    return output if output.strip() else "Script executed (no output printed)"
