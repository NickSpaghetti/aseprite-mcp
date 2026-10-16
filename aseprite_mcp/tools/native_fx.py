"""Native Aseprite filter/command wrappers (app.command.*).

These delegate to Aseprite's own engine filters instead of hand-rolling
pixel math in Lua — higher quality and faster than the equivalents in
fx.py. All verified to run headless under --batch (T0, 2026-06-18). They
are added ALONGSIDE the hand-rolled tools (outline_cel / adjust_hsl /
quantize_to_palette stay) per the "deprecate, don't break" policy.

General value (upstream-able): nothing Chimera-specific here.
"""
import json

from ..core.commands import call
from ..core.boundary import require_color, require_file
from ..core.errors import InputError
from .. import mcp

# Built-in convolution-matrix resource names (Aseprite data/convmatr.def).
CONVOLUTION_MATRICES = frozenset({
    "brightness", "contrast", "negative",
    "blur-3x3", "blur-3x3-hard", "blur-5x5", "blur-7x7", "blur-9x9", "blur-17x17",
    "blur-5x3-left", "blur-17x3-left", "blur-3x17-top",
    "blur-5x5-diagonal(\\)", "blur-5x5-diagonal(/)",
    "sharpen-3x3", "sharpen-5x5", "sharpen-7x7",
    "edges-find", "edges-find-horizontal", "edges-find-vertical",
    "misc-contour", "misc-texturize", "misc-emboss", "misc-marmolize",
    "misc-rock", "misc-rock-edges",
    "drunk-3x3_x", "drunk-3x3_+", "drunk-5x5_x", "drunk-5x5_+",
    "drunk-7x7_x", "drunk-7x7_+", "drunk-9x9_x", "drunk-9x9_+",
    "drunk-17x17_x", "drunk-17x17_+", "drunk-17x17_o",
    "outline-transparent-layer-(cross)", "outline-transparent-layer-(square)",
})


def _region(x: int, y: int, width: int, height: int) -> list[int] | None:
    """[x, y, w, h] when width and height are > 0, else None (the whole cel)."""
    return [x, y, width, height] if width > 0 and height > 0 else None


def _target(layer_name: str, frame_index: int) -> dict:
    """Empty layer_name means the default target (see lib.default_target)."""
    return {"layer": layer_name or None, "frame": frame_index}


@mcp.tool()
async def outline_native(
    filename: str,
    layer_name: str = "",
    frame_index: int = 1,
    color: str = "#000000",
    place: str = "outside",
    matrix: str = "circle",
) -> str:
    """Native Aseprite Outline around opaque pixels (app.command.Outline).

    Higher quality than the 1px hand-rolled outline_cel: inside/outside
    placement + a circle/square brush. Works best on a full-canvas cel.

    Args:
        filename: Aseprite file to modify
        layer_name: layer to outline (empty = active layer)
        frame_index: 1-based frame
        color: outline colour as #RRGGBB
        place: "outside" or "inside"
        matrix: "circle" or "square"
    """
    require_file(filename)
    color_rgba = require_color(color)[:3] + [255]
    if place not in ("outside", "inside"):
        raise InputError("place must be 'outside' or 'inside'")
    if matrix not in ("circle", "square"):
        raise InputError("matrix must be 'circle' or 'square'")

    await call("native.outline", filename, color=color_rgba, place=place, matrix=matrix,
               **_target(layer_name, frame_index))
    return f"Outlined ({place}, {matrix}) {layer_name or 'active layer'} in {filename}"


@mcp.tool()
async def adjust_hsl_native(
    filename: str,
    layer_name: str = "",
    frame_index: int = 1,
    hue: int = 0,
    saturation: int = 0,
    lightness: int = 0,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> str:
    """Native Hue/Saturation/Lightness filter (engine-quality vs adjust_hsl).

    Args:
        filename: Aseprite file to modify
        layer_name: layer to adjust (empty = active layer)
        frame_index: 1-based frame
        hue: -180..180 (degrees)
        saturation: -100..100
        lightness: -100..100
        x, y, width, height: optional region (width>0 & height>0 to scope)
    """
    require_file(filename)
    if not (-180 <= hue <= 180):
        raise InputError("hue must be -180..180")
    if not (-100 <= saturation <= 100) or not (-100 <= lightness <= 100):
        raise InputError("saturation and lightness must be -100..100")

    await call("native.hue_saturation", filename, hue=hue, saturation=saturation, lightness=lightness,
               region=_region(x, y, width, height), **_target(layer_name, frame_index))
    return f"Adjusted HSL on {layer_name or 'active layer'} in {filename}"


@mcp.tool()
async def adjust_brightness_contrast(
    filename: str,
    layer_name: str = "",
    frame_index: int = 1,
    brightness: int = 0,
    contrast: int = 0,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> str:
    """Native Brightness/Contrast filter (app.command.BrightnessContrast).

    Args:
        filename: Aseprite file to modify
        layer_name: layer to adjust (empty = active layer)
        frame_index: 1-based frame
        brightness: -100..100
        contrast: -100..100
        x, y, width, height: optional region (width>0 & height>0 to scope)
    """
    require_file(filename)
    if not (-100 <= brightness <= 100) or not (-100 <= contrast <= 100):
        raise InputError("brightness and contrast must be -100..100")

    await call("native.brightness_contrast", filename, brightness=brightness, contrast=contrast,
               region=_region(x, y, width, height), **_target(layer_name, frame_index))
    return f"Adjusted brightness/contrast on {layer_name or 'active layer'} in {filename}"


@mcp.tool()
async def invert_colors(
    filename: str,
    layer_name: str = "",
    frame_index: int = 1,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> str:
    """Native colour inversion (app.command.InvertColor).

    Args:
        filename: Aseprite file to modify
        layer_name: layer to invert (empty = active layer)
        frame_index: 1-based frame
        x, y, width, height: optional region (width>0 & height>0 to scope)
    """
    require_file(filename)

    await call("native.invert", filename, region=_region(x, y, width, height), **_target(layer_name, frame_index))
    return f"Inverted colours on {layer_name or 'active layer'} in {filename}"


@mcp.tool()
async def apply_convolution(
    filename: str,
    matrix: str,
    layer_name: str = "",
    frame_index: int = 1,
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> str:
    """Native convolution filter (blur / sharpen / edge / emboss …).

    Args:
        filename: Aseprite file to modify
        matrix: a built-in matrix name (see list_convolution_matrices),
            e.g. "blur-3x3", "sharpen-3x3", "edges-find", "misc-emboss"
        layer_name: layer to filter (empty = active layer)
        frame_index: 1-based frame
        x, y, width, height: optional region (width>0 & height>0 to scope)
    """
    require_file(filename)
    if matrix not in CONVOLUTION_MATRICES:
        raise InputError(f"Unknown matrix {matrix!r}; call list_convolution_matrices for "
                         f"the {len(CONVOLUTION_MATRICES)} valid names")

    await call("native.convolution", filename, matrix=matrix, region=_region(x, y, width, height),
               **_target(layer_name, frame_index))
    return f"Applied convolution '{matrix}' on {layer_name or 'active layer'} in {filename}"


@mcp.tool()
async def list_convolution_matrices() -> str:
    """List the built-in convolution-matrix names usable with apply_convolution.

    Returns:
        JSON array of matrix resource names.
    """
    return json.dumps(sorted(CONVOLUTION_MATRICES))


@mcp.tool()
async def extract_palette(
    filename: str,
    max_colors: int = 16,
    with_alpha: bool = False,
) -> str:
    """Build an OPTIMAL palette from the sprite via native ColorQuantization.

    True palette extraction (vs the nearest-snap quantize_to_palette): writes
    the resulting palette to the sprite and returns it. NOTE: mutates the
    sprite's palette. Sprite must be in RGB mode.

    Args:
        filename: Aseprite file to modify
        max_colors: palette size cap, 1..256 (fewer if the art has fewer)
        with_alpha: include alpha when quantizing

    Returns:
        JSON {colors: [#RRGGBB, ...], count}
    """
    require_file(filename)
    if not (1 <= max_colors <= 256):
        raise InputError("max_colors must be 1..256")

    result = await call("native.extract_palette", filename, max_colors=max_colors, with_alpha=with_alpha)
    return json.dumps({"colors": result["colors"], "count": len(result["colors"])})
