from typing import List

from ..core.commands import call
from ..core.boundary import require_file, require_safe_path
from ..core.errors import InputError
from .. import mcp


@mcp.tool()
async def copy_layers_between_sprites(
    source_filename: str,
    target_filename: str,
    layer_names: List[str],
    replace: bool = True,
    create_missing_frames: bool = True
) -> str:
    """Copy layers by name from a source sprite to a target sprite.

    Args:
        source_filename: Source .aseprite file
        target_filename: Target .aseprite file
        layer_names: List of layer names to copy
        replace: Overwrite existing cels in target layers
        create_missing_frames: Add frames to target if needed
    """
    require_file(source_filename)
    require_file(target_filename)
    if not layer_names:
        raise InputError("Layer names list cannot be empty")
    require_safe_path(source_filename)
    require_safe_path(target_filename)

    result = await call("scene.copy_layers", source=source_filename, target=target_filename, names=layer_names,
                        replace=replace, create_missing_frames=create_missing_frames)
    msg = f"Layers copied from {source_filename} to {target_filename}"
    if result["missing"]:
        msg += f" (skipped missing layers: {', '.join(result['missing'])})"
    return msg
