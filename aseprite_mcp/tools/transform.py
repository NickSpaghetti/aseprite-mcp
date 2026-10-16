from ..core.commands import call
from ..core.boundary import require_file
from ..core.errors import InputError
from .. import mcp


@mcp.tool()
async def flip_layer(
    filename: str,
    layer_name: str,
    frame_index: int,
    direction: str = "horizontal",
) -> str:
    """Flip a layer's image horizontally or vertically.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer name to flip
        frame_index: Frame index starting at 1
        direction: "horizontal" or "vertical"
    """
    require_file(filename)
    if direction not in ("horizontal", "vertical"):
        raise InputError("direction must be 'horizontal' or 'vertical'")

    await call("transform.flip", filename, layer=layer_name, frame=frame_index, direction=direction)
    return f"Layer '{layer_name}' flipped {direction}ly in {filename}"


@mcp.tool()
async def rotate_layer(
    filename: str,
    layer_name: str,
    frame_index: int,
    angle: int = 90,
) -> str:
    """Rotate a layer's image 90, 180, or 270 degrees clockwise.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer name to rotate
        frame_index: Frame index starting at 1
        angle: Rotation angle: 90, 180, or 270 (clockwise)
    """
    require_file(filename)
    if angle not in (90, 180, 270):
        raise InputError("angle must be 90, 180, or 270")

    await call("transform.rotate", filename, layer=layer_name, frame=frame_index, angle=angle)
    return f"Layer '{layer_name}' rotated {angle}° clockwise in {filename}"


@mcp.tool()
async def resize_canvas(filename: str, width: int, height: int) -> str:
    """Scale the canvas and all its content to new dimensions.

    Args:
        filename: Aseprite file to modify
        width: New canvas width in pixels
        height: New canvas height in pixels
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    await call("transform.resize", filename, width=width, height=height)
    return f"Canvas resized to {width}x{height} in {filename}"


@mcp.tool()
async def crop_canvas(filename: str, x: int, y: int, width: int, height: int) -> str:
    """Crop the canvas to the given rectangle, discarding content outside it.

    Args:
        filename: Aseprite file to modify
        x: Left edge of the crop area
        y: Top edge of the crop area
        width: Width of the crop area
        height: Height of the crop area
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    await call("transform.crop", filename, x=x, y=y, width=width, height=height)
    return f"Canvas cropped to ({x},{y}) {width}x{height} in {filename}"
