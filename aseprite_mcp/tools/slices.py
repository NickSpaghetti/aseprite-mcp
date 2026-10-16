import json

from ..core.commands import call
from ..core.boundary import require_file
from ..core.errors import InputError
from .. import mcp


@mcp.tool()
async def create_slice(
    filename: str,
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
) -> str:
    """Create a named slice (a rectangular region usable by game engines).

    Args:
        filename: Aseprite file to modify
        name: Slice name
        x: Left edge of the slice
        y: Top edge of the slice
        width: Slice width
        height: Slice height
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")
    if not name:
        raise InputError("Slice name cannot be empty")

    await call("slices.create", filename, name=name, x=x, y=y, width=width, height=height)
    return f"Slice '{name}' created at ({x},{y}) {width}x{height} in {filename}"


@mcp.tool()
async def set_slice_center(
    filename: str,
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
) -> str:
    """Set a slice's 9-patch center rectangle (relative to the slice origin).

    The center defines the stretchable region for 9-patch scaling in
    game engines.

    Args:
        filename: Aseprite file to modify
        name: Slice name
        x: Center-rect left edge, relative to the slice
        y: Center-rect top edge, relative to the slice
        width: Center-rect width
        height: Center-rect height
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    await call("slices.set_center", filename, name=name, x=x, y=y, width=width, height=height)
    return f"Slice '{name}' 9-patch center set to ({x},{y}) {width}x{height} in {filename}"


@mcp.tool()
async def set_slice_pivot(filename: str, name: str, x: int, y: int) -> str:
    """Set a slice's pivot point (relative to the slice origin).

    Args:
        filename: Aseprite file to modify
        name: Slice name
        x: Pivot x, relative to the slice
        y: Pivot y, relative to the slice
    """
    require_file(filename)

    await call("slices.set_pivot", filename, name=name, x=x, y=y)
    return f"Slice '{name}' pivot set to ({x},{y}) in {filename}"


@mcp.tool()
async def list_slices(filename: str) -> str:
    """List all slices with their bounds, 9-patch centers, and pivots.

    Returns:
        JSON array of {name, x, y, width, height, center?, pivot?}.
    """
    require_file(filename)

    result = await call("slices.list", filename)
    keys = ("name", "x", "y", "width", "height", "center", "pivot")
    return json.dumps([{k: s[k] for k in keys if k in s} for s in result["slices"]])


@mcp.tool()
async def delete_slice(filename: str, name: str) -> str:
    """Delete a slice by name.

    Args:
        filename: Aseprite file to modify
        name: Slice name to delete
    """
    require_file(filename)

    await call("slices.delete", filename, name=name)
    return f"Slice '{name}' deleted from {filename}"
