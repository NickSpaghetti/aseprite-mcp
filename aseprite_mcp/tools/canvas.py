from ..core.commands import call
from ..core.boundary import require_file, require_safe_path
from ..core.errors import AsepriteError, InputError
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
    """Check that a frame exists.

    Aseprite keeps no active frame between tool calls, so this changes
    nothing. Pass frame_index to the tool that should act on the frame.

    Args:
        filename: Name of the Aseprite file to check
        frame_index: Frame index starting at 1
    """
    require_file(filename)

    await call("canvas.check_frame", filename, frame=frame_index)
    return (f"Frame {frame_index} exists in {filename}. Aseprite keeps no active frame between calls, "
            f"so pass frame_index to the tool that should use it.")

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
    """Check that a layer exists, optionally creating it.

    Aseprite keeps no active layer between tool calls, so this does not make
    the layer "active". Pass layer_name to the tool that should act on it.
    The file only changes when create_if_missing creates the layer.

    Args:
        filename: Name of the Aseprite file to check
        layer_name: Layer name, or "group/layer" path
        create_if_missing: Create a top-level layer with this name if none exists
    """
    require_file(filename)

    note = "Aseprite keeps no active layer between calls, so pass layer_name to the tool that should use it."
    if (await call("canvas.layer_exists", filename, name=layer_name))["exists"]:
        return f"Layer '{layer_name}' exists in {filename}. {note}"
    if not create_if_missing:
        raise AsepriteError("Layer not found", code="LayerNotFound")
    await call("canvas.add_layer", filename, name=layer_name)
    return f"Layer '{layer_name}' created in {filename}. {note}"
