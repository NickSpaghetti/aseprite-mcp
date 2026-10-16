from ..core.commands import call
from ..core.boundary import require_color, require_file
from ..core.errors import InputError
from .. import mcp


def _region(x: int, y: int, width: int, height: int) -> dict:
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")
    return {"x": x, "y": y, "width": width, "height": height}


@mcp.tool()
async def move_region(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    dest_x: int,
    dest_y: int,
) -> str:
    """Cut a rectangular region of pixels and paste it at a new position.

    Coordinates are sprite-global. The source area is left transparent.
    Pixels moved outside the canvas are discarded. Fully transparent
    source pixels do not overwrite destination pixels.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to operate on
        frame_index: Frame index starting at 1
        x: Left edge of the source region
        y: Top edge of the source region
        width: Region width
        height: Region height
        dest_x: New left edge for the region
        dest_y: New top edge for the region
    """
    require_file(filename)
    region = _region(x, y, width, height)

    await call("selection.move", filename, layer=layer_name, frame=frame_index, dest_x=dest_x, dest_y=dest_y,
               **region)
    return (
        f"Moved {width}x{height} region from ({x},{y}) to ({dest_x},{dest_y}) "
        f"on '{layer_name}' frame {frame_index} in {filename}"
    )


@mcp.tool()
async def copy_region(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    dest_x: int,
    dest_y: int,
    target_layer_name: str = "",
    target_frame_index: int = 0,
) -> str:
    """Copy a rectangular region of pixels to another position, layer, or frame.

    Coordinates are sprite-global. Fully transparent source pixels do not
    overwrite destination pixels. The destination cel is created when missing.

    Args:
        filename: Aseprite file to modify
        layer_name: Source layer
        frame_index: Source frame index starting at 1
        x: Left edge of the source region
        y: Top edge of the source region
        width: Region width
        height: Region height
        dest_x: Left edge of the destination
        dest_y: Top edge of the destination
        target_layer_name: Destination layer (default: same as source)
        target_frame_index: Destination frame (default: same as source)
    """
    require_file(filename)
    region = _region(x, y, width, height)

    await call("selection.copy", filename, layer=layer_name, frame=frame_index,
               target_layer=target_layer_name or layer_name,
               target_frame=target_frame_index if target_frame_index >= 1 else frame_index,
               dest_x=dest_x, dest_y=dest_y, **region)
    return (
        f"Copied {width}x{height} region from ({x},{y}) to ({dest_x},{dest_y}) "
        f"in {filename}"
    )


@mcp.tool()
async def erase_region(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
) -> str:
    """Erase (make transparent) a rectangular region of pixels.

    Coordinates are sprite-global.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to operate on
        frame_index: Frame index starting at 1
        x: Left edge of the region
        y: Top edge of the region
        width: Region width
        height: Region height
    """
    require_file(filename)
    region = _region(x, y, width, height)

    await call("selection.erase", filename, layer=layer_name, frame=frame_index, **region)
    return (
        f"Erased {width}x{height} region at ({x},{y}) on '{layer_name}' "
        f"frame {frame_index} in {filename}"
    )


@mcp.tool()
async def erase_color(
    filename: str,
    layer_name: str,
    frame_index: int,
    color: str,
    tolerance: int = 0,
) -> str:
    """Make all pixels of a given color transparent (like a magic eraser).

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to operate on
        frame_index: Frame index starting at 1
        color: Hex color to erase, e.g. "#FF00FF"
        tolerance: Per-channel tolerance 0-255 (default 0 = exact match)
    """
    require_file(filename)
    target = require_color(color)
    if tolerance < 0 or tolerance > 255:
        raise InputError("Tolerance must be between 0 and 255")

    result = await call("selection.erase_color", filename, layer=layer_name, frame=frame_index,
                        color=target, tolerance=tolerance)
    return (
        f"Erased {result['count']} pixels of {color} on '{layer_name}' "
        f"frame {frame_index} in {filename}"
    )
