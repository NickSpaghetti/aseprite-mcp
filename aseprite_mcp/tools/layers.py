from ..core.commands import call
from ..core.boundary import require_file
from ..core.errors import InputError
from .. import mcp

# Tool-facing blend mode name -> Aseprite's BlendMode constant.
_BLEND_MODES = {
    "normal": "NORMAL",
    "darken": "DARKEN",
    "multiply": "MULTIPLY",
    "color_burn": "COLOR_BURN",
    "lighten": "LIGHTEN",
    "screen": "SCREEN",
    "color_dodge": "COLOR_DODGE",
    "addition": "ADDITION",
    "overlay": "OVERLAY",
    "soft_light": "SOFT_LIGHT",
    "hard_light": "HARD_LIGHT",
    "difference": "DIFFERENCE",
    "exclusion": "EXCLUSION",
    "subtract": "SUBTRACT",
    "divide": "DIVIDE",
    "hue": "HSL_HUE",
    "saturation": "HSL_SATURATION",
    "color": "HSL_COLOR",
    "luminosity": "HSL_LUMINOSITY",
}


@mcp.tool()
async def delete_layer(filename: str, layer_name: str) -> str:
    """Delete a layer by name.

    Args:
        filename: Aseprite file to modify
        layer_name: Name of the layer to delete
    """
    require_file(filename)

    await call("layers.delete", filename, name=layer_name)
    return f"Layer '{layer_name}' deleted from {filename}"


@mcp.tool()
async def rename_layer(filename: str, layer_name: str, new_name: str) -> str:
    """Rename a layer.

    Args:
        filename: Aseprite file to modify
        layer_name: Current layer name
        new_name: New layer name
    """
    require_file(filename)
    if not new_name:
        raise InputError("New name cannot be empty")

    await call("layers.rename", filename, name=layer_name, new_name=new_name)
    return f"Layer '{layer_name}' renamed to '{new_name}' in {filename}"


@mcp.tool()
async def duplicate_layer(
    filename: str, layer_name: str, new_name: str = "", group: str = ""
) -> str:
    """Duplicate a layer with all its cels across every frame.

    The copy inherits the source's opacity and blend mode. By default it is
    placed directly above the source layer; pass `group` to place it inside a
    group instead.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to duplicate, by name or "group/subgroup/layer" path
        new_name: Name for the copy (default: "<layer_name> copy")
        group: Optional group to place the copy inside, by name or
            "group/subgroup" path (default: directly above the source)
    """
    require_file(filename)

    final_name = new_name or f"{layer_name} copy"
    await call("layers.duplicate", filename, name=layer_name, new_name=final_name, group=group or None)
    location = f" inside group '{group}'" if group else ""
    return f"Layer '{layer_name}' duplicated as '{final_name}'{location} in {filename}"


@mcp.tool()
async def reorder_layer(filename: str, layer_name: str, position: int) -> str:
    """Move a layer to a new position in the layer stack.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to move
        position: Target stack position, 1-based where 1 is the bottom layer
    """
    require_file(filename)
    if position < 1:
        raise InputError("Position must be >= 1")

    await call("layers.reorder", filename, name=layer_name, position=position)
    return f"Layer '{layer_name}' moved to position {position} in {filename}"


@mcp.tool()
async def set_layer_blend_mode(filename: str, layer_name: str, mode: str) -> str:
    """Set a layer's blend mode.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to modify
        mode: One of: normal, darken, multiply, color_burn, lighten, screen,
            color_dodge, addition, overlay, soft_light, hard_light,
            difference, exclusion, subtract, divide, hue, saturation,
            color, luminosity
    """
    require_file(filename)

    blend = _BLEND_MODES.get(mode.lower())
    if blend is None:
        raise InputError(f"Unknown blend mode '{mode}'. Valid modes: {', '.join(sorted(_BLEND_MODES))}")

    await call("layers.set_blend_mode", filename, name=layer_name, mode=blend)
    return f"Layer '{layer_name}' blend mode set to {mode} in {filename}"


@mcp.tool()
async def merge_layer_down(filename: str, layer_name: str) -> str:
    """Merge a layer into the layer directly below it.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to merge down (must not be the bottom layer)
    """
    require_file(filename)

    await call("layers.merge_down", filename, name=layer_name)
    return f"Layer '{layer_name}' merged down in {filename}"


@mcp.tool()
async def flatten_sprite(filename: str) -> str:
    """Flatten all layers into a single layer.

    Args:
        filename: Aseprite file to modify
    """
    require_file(filename)

    await call("layers.flatten", filename)
    return f"Sprite flattened in {filename}"
