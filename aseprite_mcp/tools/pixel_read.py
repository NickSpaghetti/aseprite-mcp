import json

from ..core.commands import call
from ..core.boundary import require_file
from ..core.errors import InputError
from .. import mcp


def _describe(pixel: list[int]) -> str:
    _, _, r, g, b, a = pixel
    return f"#{r:02x}{g:02x}{b:02x} (r={r}, g={g}, b={b}, a={a})"


def _as_json(pixels: list[list[int]]) -> str:
    return json.dumps([
        {"x": x, "y": y, "hex": f"#{r:02x}{g:02x}{b:02x}", "r": r, "g": g, "b": b, "a": a}
        for x, y, r, g, b, a in pixels
    ])


@mcp.tool()
async def get_pixel_color(
    filename: str,
    x: int,
    y: int,
    layer_name: str = "",
    frame_index: int = 1,
) -> str:
    """Read the RGBA color of a single pixel.

    Args:
        filename: Aseprite file to read
        x: X coordinate
        y: Y coordinate
        layer_name: Layer to read from (empty = the sprite's only layer; required
            when there are several)
        frame_index: Frame index starting at 1
    """
    require_file(filename)

    result = await call("pixel_read.cel", filename, layer=layer_name or None, frame=frame_index,
                        x=x, y=y, width=1, height=1)
    return _describe(result["pixels"][0])


@mcp.tool()
async def get_pixels_rect(
    filename: str,
    x: int,
    y: int,
    width: int,
    height: int,
    layer_name: str = "",
    frame_index: int = 1,
) -> str:
    """Read all pixel colors in a rectangular region.

    Args:
        filename: Aseprite file to read
        x: Top-left x coordinate
        y: Top-left y coordinate
        width: Width of the region
        height: Height of the region
        layer_name: Layer to read from (empty = the sprite's only layer; required
            when there are several)
        frame_index: Frame index starting at 1

    Returns:
        JSON array of {x, y, hex, r, g, b, a} objects
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    result = await call("pixel_read.cel", filename, layer=layer_name or None, frame=frame_index,
                        x=x, y=y, width=width, height=height)
    return _as_json(result["pixels"])


@mcp.tool()
async def get_composite_pixel(filename: str, x: int, y: int, frame_index: int = 1) -> str:
    """Read the RGBA colour VISIBLE at a pixel (flattened composite of all layers).

    Unlike get_pixel_color (which reads a single cel), this composites every
    visible layer — "what the player actually sees". Hidden layers are left
    out; layer opacity and blend modes apply. Essential for value/CVD QA on grouped/multi-layer scenes.

    Args:
        filename: Aseprite file to read
        x: X coordinate (sprite-global)
        y: Y coordinate (sprite-global)
        frame_index: Frame index starting at 1
    """
    require_file(filename)

    result = await call("pixel_read.composite", filename, frame=frame_index, x=x, y=y, width=1, height=1)
    return _describe(result["pixels"][0])


@mcp.tool()
async def get_composite_rect(
    filename: str,
    x: int,
    y: int,
    width: int,
    height: int,
    frame_index: int = 1,
) -> str:
    """Read VISIBLE RGBA over a rectangle (flattened composite of all layers).

    The rectangular counterpart of get_composite_pixel — reads the composited
    pixels every visible layer produces, not a single cel.

    Args:
        filename: Aseprite file to read
        x: Top-left x (sprite-global)
        y: Top-left y (sprite-global)
        width: Region width
        height: Region height
        frame_index: Frame index starting at 1

    Returns:
        JSON array of {x, y, hex, r, g, b, a} objects
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    result = await call("pixel_read.composite", filename, frame=frame_index, x=x, y=y, width=width, height=height)
    return _as_json(result["pixels"])
