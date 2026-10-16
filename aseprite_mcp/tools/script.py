from ..core.commands import run_script
from ..core.boundary import require_file
from ..core.errors import InputError
from .. import mcp


@mcp.tool()
async def run_lua_script(script: str, filename: str = "") -> str:
    """Execute arbitrary Aseprite Lua code in batch mode (escape hatch).

    Use this when no dedicated tool covers what you need. The full API
    is documented at https://www.aseprite.org/api/. Anything the curated
    tools do can also be done here — they are Lua underneath.

    Essentials for batch-mode scripts:
    - When filename is given, it is opened first and available as
      app.activeSprite.
    - Changes are NOT saved automatically; call spr:saveAs(spr.filename)
      at the end if you modified the sprite.
    - print() is the only way to return data; a clean exit does not mean
      your logic succeeded, so print what you need to verify.
    - Coordinates on cel images are cel-local: offset sprite-global
      coordinates by cel.position before getPixel/putPixel.

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
