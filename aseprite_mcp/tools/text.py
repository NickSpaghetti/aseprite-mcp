"""Text drawing.

Aseprite exposes no text API to Lua, so glyphs are rasterised here and the
result is blitted into the sprite as an image.
"""

from typing import Optional

from ..core.commands import call
from ..core.boundary import require_color, require_file
from ..core.errors import InputError
from ..core import fonts as fontlib
from .. import mcp

_ANCHORS = (
    "topleft", "top", "topright",
    "left", "center", "right",
    "bottomleft", "bottom", "bottomright",
    "baselineleft", "baseline", "baselineright",
)


def _text_origin(anchor: str, x: int, y: int, metrics: dict) -> tuple[int, int]:
    """Map an anchor point to the pen origin the glyph run should start from.

    Ink coordinates run from the pen origin on x and from the baseline on y, so
    the baseline* anchors need no vertical correction at all while the box
    anchors are offset by the ink extents.
    """
    width, height = metrics["width"], metrics["height"]

    if anchor.endswith("right"):
        x -= width
    elif anchor in ("top", "center", "bottom", "baseline"):
        x -= width // 2
    origin_x = x - metrics["left"]

    if anchor.startswith("baseline"):
        return origin_x, y
    if anchor.startswith("bottom"):
        y -= height
    elif anchor in ("left", "center", "right"):
        y -= height // 2
    return origin_x, y - metrics["top"]


def _compose_stamp(
    ink: set,
    fill: list[int],
    outline: list[int] | None = None,
    outline_width: int = 1,
    outline_diagonal: bool = True,
    shadow: list[int] | None = None,
    shadow_dx: int = 1,
    shadow_dy: int = 1,
) -> dict:
    """Layer shadow, outline and ink into one stamp.

    `ink` is a set of (x, y) relative to the pen origin. Returns the stamp's
    offset from the pen origin (`left`, `top`), its `width` and `height`, and
    `pixels` as [x, y, colour_index] inside the stamp with `colors` holding
    the RGBA per index. Back to front: shadow, then outline, then ink.
    """
    rim = set()
    if outline:
        rim = set(ink)
        for _ in range(max(1, outline_width)):
            grown = set(rim)
            for px, py in rim:
                grown.update({(px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)})
                if outline_diagonal:
                    grown.update({(px - 1, py - 1), (px + 1, py - 1), (px - 1, py + 1), (px + 1, py + 1)})
            rim = grown
        rim -= ink
    drop = {(px + shadow_dx, py + shadow_dy) for px, py in ink} - ink - rim if shadow else set()

    everything = ink | rim | drop
    left = min(p[0] for p in everything)
    top = min(p[1] for p in everything)
    colors, pixels = [], []
    for points, rgba in ((drop, shadow), (rim, outline), (ink, fill)):
        if not points:
            continue
        colors.append(rgba)
        pixels += [[x - left, y - top, len(colors)] for x, y in sorted(points)]
    return {
        "left": left, "top": top,
        "width": max(p[0] for p in everything) - left + 1,
        "height": max(p[1] for p in everything) - top + 1,
        "pixels": pixels, "colors": colors,
    }


@mcp.tool()
async def list_text_fonts() -> str:
    """List fonts that draw_text can use.

    Covers bitmap sprite-sheet fonts and .ttf/.otf files installed under
    ~/.aseprite-mcp/fonts, plus TrueType fonts found in the system font
    directories. Bitmap fonts are the right choice for pixel art: their
    glyphs are already pixels and `size` scales them by whole numbers.
    """
    found = fontlib.available_fonts()
    if not found:
        return "No fonts found. Drop a .ttf into ~/.aseprite-mcp/fonts/."

    user = [f for f in found if f["source"] == "user"]
    system = [f for f in found if f["source"] == "system"]
    lines = []
    if user:
        lines.append("User fonts (~/.aseprite-mcp/fonts):")
        lines += [f"  {f['name']}  [{f['kind']}]" for f in user]
    if system:
        lines.append(f"System fonts ({len(system)}, all truetype):")
        lines += [f"  {f['name']}" for f in system]
    return "\n".join(lines)


@mcp.tool()
async def measure_text(
    text: str,
    font: str,
    size: int = 1,
    letter_spacing: int = 0,
    bold: int = 0,
    antialias: bool = False,
) -> str:
    """Measure text without drawing it.

    Use this to size a panel or centre a label in one shot instead of
    guessing and re-rendering.

    Args:
        text: The string to measure
        font: Font name from list_text_fonts, or a path to a .ttf/.otf or
            bitmap font directory
        size: Pixel size for TrueType fonts; integer scale factor for bitmap
            fonts (default 1)
        letter_spacing: Extra pixels between glyphs (default 0)
        bold: Faux-bold passes; each grows strokes by 1px (default 0)
        antialias: Keep greyscale edges instead of hard pixels (default False)

    Returns:
        width, height, advance_width, and the ink extents above/below the
        baseline.
    """
    try:
        f = fontlib.load_font(font)
        _, m = fontlib.shape(text, f, size, letter_spacing, bold, antialias)
    except fontlib.FontError as exc:
        raise InputError(str(exc)) from exc
    return (
        f"width={m['width']} height={m['height']} advance_width={m['advance_width']} "
        f"above_baseline={-m['top']} below_baseline={m['bottom'] + 1} "
        f"left_bearing={m['left']}"
    )


@mcp.tool()
async def draw_text(
    filename: str,
    text: str,
    x: int,
    y: int,
    font: str,
    size: int = 1,
    color: str = "#FFFFFF",
    layer_name: Optional[str] = None,
    frame_index: int = 1,
    anchor: str = "topleft",
    letter_spacing: int = 0,
    bold: int = 0,
    outline_color: Optional[str] = None,
    outline_width: int = 1,
    outline_diagonal: bool = True,
    shadow_color: Optional[str] = None,
    shadow_dx: int = 1,
    shadow_dy: int = 1,
    antialias: bool = False,
    create_if_missing: bool = True,
) -> str:
    """Draw text onto a sprite.

    Glyphs are rasterised outside Aseprite and composited in, because the
    Lua API has no text drawing of its own.

    Args:
        filename: Aseprite file to modify
        text: String to draw
        x: X coordinate of the anchor point
        y: Y coordinate of the anchor point
        font: Font name from list_text_fonts, or a path to a .ttf/.otf or a
            bitmap font directory
        size: Pixel size for TrueType fonts; integer scale factor for bitmap
            fonts (default 1)
        color: Text colour, #RRGGBB or #RRGGBBAA (default white)
        layer_name: Layer to draw on; the active/first layer if omitted
        frame_index: Frame index starting at 1 (default 1)
        anchor: Which point of the text (x, y) refers to - one of topleft,
            top, topright, left, center, right, bottomleft, bottom,
            bottomright, baselineleft, baseline, baselineright
            (default topleft)
        letter_spacing: Extra pixels between glyphs (default 0)
        bold: Faux-bold passes; each grows strokes by 1px (default 0)
        outline_color: If set, draw a 1px outline in this colour
        outline_width: Outline thickness in pixels (default 1)
        outline_diagonal: Include diagonal neighbours in the outline, giving a
            rounded corner; False gives a boxier 4-way outline (default True)
        shadow_color: If set, draw a drop shadow in this colour
        shadow_dx: Shadow X offset (default 1)
        shadow_dy: Shadow Y offset (default 1)
        antialias: Keep greyscale edges instead of hard pixels (default False)
        create_if_missing: Create the layer/cel if absent (default True)
    """
    require_file(filename)
    if anchor not in _ANCHORS:
        raise InputError(f"Invalid anchor '{anchor}'. Expected one of: {', '.join(sorted(_ANCHORS))}")
    fill = require_color(color)
    outline_rgba = require_color(outline_color, "outline_color") if outline_color else None
    shadow_rgba = require_color(shadow_color, "shadow_color") if shadow_color else None

    try:
        f = fontlib.load_font(font)
        ink, metrics = fontlib.shape(text, f, size, letter_spacing, bold, antialias)
    except fontlib.FontError as exc:
        raise InputError(str(exc)) from exc
    if not ink:
        return "OK: nothing to draw (text has no visible glyphs)"

    stamp = _compose_stamp(ink, fill, outline_rgba, outline_width, outline_diagonal,
                           shadow_rgba, shadow_dx, shadow_dy)
    # The anchor is resolved against the glyph box alone, so adding an outline
    # or a shadow never shifts where the letters themselves land.
    origin_x, origin_y = _text_origin(anchor, x, y, metrics)
    blit_x, blit_y = origin_x + stamp["left"], origin_y + stamp["top"]

    await call("text.draw", filename, layer=layer_name or None, frame=frame_index, create=create_if_missing,
               x=blit_x, y=blit_y, width=stamp["width"], height=stamp["height"],
               pixels=stamp["pixels"], colors=stamp["colors"])
    return (f"Drew '{text}' at ({blit_x}, {blit_y}), "
            f"text box {metrics['width']}x{metrics['height']}, stamp {stamp['width']}x{stamp['height']}")
