from ..core.commands import call
from ..core.boundary import require_color, require_file
from ..core.errors import InputError
from .. import mcp


def _opaque_color(value: str, field: str) -> list[int]:
    """These effects paint opaque pixels: any alpha in the colour is ignored."""
    return require_color(value, field)[:3] + [255]


@mcp.tool()
async def outline_cel(
    filename: str,
    layer_name: str,
    frame_index: int,
    color: str = "#000000",
    include_diagonals: bool = False,
) -> str:
    """Add a 1px outline around all opaque pixels of a cel.

    Transparent pixels adjacent to opaque pixels are filled with the
    outline color. Great for making sprites read clearly against any
    background.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to outline
        frame_index: Frame index starting at 1
        color: Outline hex color (default black)
        include_diagonals: Also outline diagonal neighbors for a thicker,
            rounded outline (default False)
    """
    require_file(filename)

    await call("fx.outline", filename, layer=layer_name, frame=frame_index,
               color=_opaque_color(color, "color"), diagonals=include_diagonals)
    return f"Outline added to '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def replace_color(
    filename: str,
    layer_name: str,
    frame_index: int,
    from_color: str,
    to_color: str,
    tolerance: int = 0,
) -> str:
    """Replace one color with another in a cel, preserving alpha.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to operate on
        frame_index: Frame index starting at 1
        from_color: Hex color to replace, e.g. "#FF0000"
        to_color: Replacement hex color
        tolerance: Per-channel tolerance 0-255 (default 0 = exact match)
    """
    require_file(filename)
    source = require_color(from_color, "from_color")
    target = require_color(to_color, "to_color")
    if tolerance < 0 or tolerance > 255:
        raise InputError("Tolerance must be between 0 and 255")

    result = await call("fx.replace_color", filename, layer=layer_name, frame=frame_index,
                        from_color=source, to_color=target, tolerance=tolerance)
    return (
        f"Replaced {result['count']} pixels {from_color} -> {to_color} on '{layer_name}' "
        f"frame {frame_index} in {filename}"
    )


@mcp.tool()
async def adjust_hsl(
    filename: str,
    layer_name: str,
    frame_index: int,
    hue_shift: float = 0,
    saturation_shift: float = 0,
    lightness_shift: float = 0,
) -> str:
    """Shift hue, saturation, and lightness of all opaque pixels in a cel.

    Useful for creating palette-swapped variants and shading: e.g. darken
    a duplicated layer for shadows or hue-shift toward blue for night
    scenes.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to adjust
        frame_index: Frame index starting at 1
        hue_shift: Degrees to rotate hue, -360 to 360
        saturation_shift: Saturation delta, -100 to 100
        lightness_shift: Lightness delta, -100 to 100
    """
    require_file(filename)
    if not (-360 <= hue_shift <= 360):
        raise InputError("hue_shift must be between -360 and 360")
    if not (-100 <= saturation_shift <= 100):
        raise InputError("saturation_shift must be between -100 and 100")
    if not (-100 <= lightness_shift <= 100):
        raise InputError("lightness_shift must be between -100 and 100")

    await call("fx.adjust_hsl", filename, layer=layer_name, frame=frame_index,
               hue=hue_shift, saturation=saturation_shift, lightness=lightness_shift)
    return (
        f"Adjusted HSL (h{hue_shift:+g}, s{saturation_shift:+g}, l{lightness_shift:+g}) "
        f"on '{layer_name}' frame {frame_index} in {filename}"
    )


@mcp.tool()
async def apply_dither_gradient(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    color_start: str,
    color_end: str,
    horizontal: bool = False,
    create_if_missing: bool = True,
) -> str:
    """Fill a rectangle with a two-color gradient using Bayer 4x4 ordered dithering.

    This is the classic pixel-art way to blend two colors without
    introducing new intermediate colors. The gradient runs from
    color_start (top/left) to color_end (bottom/right).

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to draw on
        frame_index: Frame index starting at 1
        x: Left edge of the rectangle
        y: Top edge of the rectangle
        width: Rectangle width
        height: Rectangle height
        color_start: Hex color at the start of the gradient
        color_end: Hex color at the end of the gradient
        horizontal: Run the gradient left-to-right instead of top-to-bottom
        create_if_missing: Create the cel if it does not exist
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    await call("fx.dither_gradient", filename, layer=layer_name, frame=frame_index, create=create_if_missing,
               x=x, y=y, width=width, height=height, horizontal=horizontal,
               color_start=_opaque_color(color_start, "color_start"),
               color_end=_opaque_color(color_end, "color_end"))
    direction = "horizontal" if horizontal else "vertical"
    return (
        f"Dithered {direction} gradient {color_start} -> {color_end} applied at "
        f"({x},{y}) {width}x{height} on '{layer_name}' frame {frame_index} in {filename}"
    )


@mcp.tool()
async def apply_dither_pattern(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    color_a: str,
    color_b: str,
    density: float = 0.5,
    create_if_missing: bool = True,
) -> str:
    """Fill a rectangle with a uniform Bayer-dithered mix of two colors.

    density controls the ratio: 0.0 = all color_a, 0.5 = checkerboard,
    1.0 = all color_b. Useful for textures (stone, grass) and flat
    mid-tones between two palette colors.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to draw on
        frame_index: Frame index starting at 1
        x: Left edge of the rectangle
        y: Top edge of the rectangle
        width: Rectangle width
        height: Rectangle height
        color_a: Base hex color
        color_b: Mixed-in hex color
        density: Fraction of color_b, 0.0-1.0 (default 0.5)
        create_if_missing: Create the cel if it does not exist
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")
    if not (0 <= density <= 1):
        raise InputError("density must be between 0.0 and 1.0")

    await call("fx.dither_pattern", filename, layer=layer_name, frame=frame_index, create=create_if_missing,
               x=x, y=y, width=width, height=height, density=density,
               color_a=_opaque_color(color_a, "color_a"), color_b=_opaque_color(color_b, "color_b"))
    return (
        f"Dither pattern ({color_a}/{color_b}, density {density}) applied at "
        f"({x},{y}) {width}x{height} on '{layer_name}' frame {frame_index} in {filename}"
    )
