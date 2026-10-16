from ..core.commands import call
from ..core.boundary import require_file, require_safe_path
from ..core.errors import InputError
from .. import mcp

@mcp.tool()
async def create_canvas(width: int, height: int, filename: str = "canvas.aseprite") -> str:
    """Create a new Aseprite canvas with specified dimensions.

    Args:
        width: Width of the canvas in pixels
        height: Height of the canvas in pixels
        filename: Name of the output file (default: canvas.aseprite)
    """
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")
    require_safe_path(filename)

    await call("canvas.create", width=width, height=height, filename=filename)
    return f"Canvas created successfully: {filename}"

@mcp.tool()
async def add_layer(filename: str, layer_name: str, group: str = "") -> str:
    """Add a new layer to the Aseprite file.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Name of the new layer
        group: Optional group to place the new layer inside, by name or
            "group/subgroup" path (default: top level)
    """
    require_file(filename)

    await call("canvas.add_layer", filename, name=layer_name, group=group or None)
    location = f" inside group '{group}'" if group else ""
    return f"Layer '{layer_name}' added{location} to {filename}"

@mcp.tool()
async def add_group(filename: str, group_name: str, parent_group: str = "") -> str:
    """Add a new, empty group layer.

    Combine with add_layer(group=...) / duplicate_layer(group=...) to build a
    grouped layer structure.

    Args:
        filename: Name of the Aseprite file to modify
        group_name: Name of the new group
        parent_group: Optional existing group to nest the new group inside, by
            name or "group/subgroup" path (default: top level)
    """
    require_file(filename)

    await call("canvas.add_group", filename, name=group_name, parent=parent_group or None)
    location = f" inside '{parent_group}'" if parent_group else ""
    return f"Group '{group_name}' created{location} in {filename}"

@mcp.tool()
async def add_frame(filename: str) -> str:
    """Add a new frame to the Aseprite file.

    Args:
        filename: Name of the Aseprite file to modify
    """
    require_file(filename)

    await call("canvas.add_frame", filename)
    return f"New frame added successfully to {filename}"

@mcp.tool()
async def set_frame(filename: str, frame_index: int) -> str:
    """Set the active frame by index (1-based).

    Args:
        filename: Name of the Aseprite file to modify
        frame_index: Frame index starting at 1
    """
    require_file(filename)

    await call("canvas.set_frame", filename, frame=frame_index)
    return f"Active frame set to {frame_index} in {filename}"

@mcp.tool()
async def set_frame_duration(filename: str, frame_index: int, duration_ms: int) -> str:
    """Set the duration of a frame in milliseconds.

    Args:
        filename: Name of the Aseprite file to modify
        frame_index: Frame index starting at 1
        duration_ms: Duration in milliseconds
    """
    require_file(filename)
    if duration_ms <= 0:
        raise InputError("Duration must be > 0")

    await call("canvas.set_frame_duration", filename, frame=frame_index, duration_ms=duration_ms)
    return f"Frame {frame_index} duration set to {duration_ms}ms in {filename}"

@mcp.tool()
async def set_layer(filename: str, layer_name: str, create_if_missing: bool = False) -> str:
    """Set the active layer by name.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to activate
        create_if_missing: Create layer if it does not exist
    """
    require_file(filename)

    await call("canvas.set_layer", filename, name=layer_name, create_if_missing=create_if_missing)
    return f"Active layer set to '{layer_name}' in {filename}"
