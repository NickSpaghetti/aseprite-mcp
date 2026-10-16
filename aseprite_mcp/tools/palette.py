import colorsys
import json
from typing import List

from ..core.commands import call
from ..core.boundary import require_color, require_file
from ..core.errors import InputError
from .. import mcp

# Well-known retro/pixel-art palettes.
PALETTE_PRESETS = {
    "gameboy": ["#0F380F", "#306230", "#8BAC0F", "#9BBC0F"],
    "monochrome": ["#000000", "#FFFFFF"],
    "grayscale_4": ["#000000", "#555555", "#AAAAAA", "#FFFFFF"],
    "cga": ["#000000", "#55FFFF", "#FF55FF", "#FFFFFF"],
    "pico8": [
        "#000000", "#1D2B53", "#7E2553", "#008751",
        "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
        "#FF004D", "#FFA300", "#FFEC27", "#00E436",
        "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA",
    ],
    "c64": [
        "#000000", "#FFFFFF", "#880000", "#AAFFEE",
        "#CC44CC", "#00CC55", "#0000AA", "#EEEE77",
        "#DD8855", "#664400", "#FF7777", "#333333",
        "#777777", "#AAFF66", "#0088FF", "#BBBBBB",
    ],
    "dawnbringer16": [
        "#140C1C", "#442434", "#30346D", "#4E4A4E",
        "#854C30", "#346524", "#D04648", "#757161",
        "#597DCE", "#D27D2C", "#8595A1", "#6DAA2C",
        "#D2AA99", "#6DC2CA", "#DAD45E", "#DEEED6",
    ],
    "dawnbringer32": [
        "#000000", "#222034", "#45283C", "#663931",
        "#8F563B", "#DF7126", "#D9A066", "#EEC39A",
        "#FBF236", "#99E550", "#6ABE30", "#37946E",
        "#4B692F", "#524B24", "#323C39", "#3F3F74",
        "#306082", "#5B6EE1", "#639BFF", "#5FCDE4",
        "#CBDBFC", "#FFFFFF", "#9BADB7", "#847E87",
        "#696A6A", "#595652", "#76428A", "#AC3232",
        "#D95763", "#D77BBA", "#8F974A", "#8A6F30",
    ],
}

def _mapping(m: dict) -> list[list[int]]:
    """{"from": hex, "to": hex} -> [[r, g, b, a], [r, g, b, a]]."""
    if not isinstance(m, dict):
        raise InputError(f"Each mapping must be an object with 'from' and 'to' colours, got {m!r}")
    return [require_color(m.get("from"), "mapping 'from'"), require_color(m.get("to"), "mapping 'to'")]


@mcp.tool()
async def get_palette(filename: str) -> str:
    """Get the active sprite palette as a JSON array of hex colors."""
    require_file(filename)

    result = await call("palette.get", filename)
    return json.dumps(result["colors"])


@mcp.tool()
async def set_palette(filename: str, colors: List[str]) -> str:
    """Set the active sprite palette using a list of hex colors."""
    require_file(filename)
    if not colors:
        raise InputError("Colors list cannot be empty")

    await call("palette.set", filename, colors=[require_color(c) for c in colors])
    return f"Palette set with {len(colors)} colors in {filename}"


@mcp.tool()
async def remap_colors_in_cel_range(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    mappings: List[dict],
    create_missing_cels: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Remap colors in a layer across a frame range using explicit mappings.

    Args:
        filename (str): The path to the Aseprite file.
        layer_name (str): The name of the layer to remap colors in.
        start_frame (int): The start frame index to remap colors in.
        end_frame (int): The end frame index to remap colors in.
        mappings (List[dict]): The color mappings to use.
        create_missing_cels (bool, optional): Whether to create missing cels. Defaults to False.
        source_frame_index (int | None, optional): The source frame index to use for remapping. Defaults to None.
    """
    require_file(filename)
    if not mappings:
        raise InputError("Mappings list cannot be empty")

    await call("palette.remap", filename, layer=layer_name, first=start_frame, last=end_frame,
               mappings=[_mapping(m) for m in mappings], create_missing=create_missing_cels,
               source_frame=source_frame_index)
    return (
        f"Remapped colors on '{layer_name}' frames {start_frame}-{end_frame} in {filename}"
    )


@mcp.tool()
async def list_palette_presets() -> str:
    """List the built-in retro palette presets with their colors.

    Returns:
        JSON object mapping preset name to its list of hex colors.
    """
    return json.dumps(PALETTE_PRESETS, indent=2)


@mcp.tool()
async def apply_palette_preset(filename: str, preset: str) -> str:
    """Set the sprite palette to a built-in retro preset.

    This only sets the palette; existing pixels keep their colors.
    Use quantize_to_palette afterwards to snap pixels to the new palette.

    Args:
        filename: Aseprite file to modify
        preset: One of: gameboy, monochrome, grayscale_4, cga, pico8, c64,
            dawnbringer16, dawnbringer32
    """
    colors = PALETTE_PRESETS.get(preset.lower())
    if colors is None:
        raise InputError(f"Unknown preset '{preset}'. Available: {', '.join(sorted(PALETTE_PRESETS))}")
    require_file(filename)

    await call("palette.set", filename, colors=[require_color(c) for c in colors])
    return f"Palette preset '{preset}' ({len(colors)} colors) applied to {filename}"


@mcp.tool()
async def generate_color_ramp(
    base_color: str,
    steps: int = 5,
    hue_shift_degrees: float = 20,
    lightness_range: float = 0.5,
) -> str:
    """Generate a shading ramp (dark to light) from a base color.

    Produces the standard pixel-art shading technique of hue-shifting:
    shadows lean cooler (hue shifted one way), highlights lean warmer.
    Use the returned colors for shading instead of plain darker/lighter
    versions of the same hue.

    Args:
        base_color: Hex color the ramp is built around, e.g. "#D04648"
        steps: Number of colors in the ramp, 2-16 (default 5)
        hue_shift_degrees: Total hue rotation across the ramp (default 20)
        lightness_range: Total lightness span across the ramp, 0-1 (default 0.5)

    Returns:
        JSON array of hex colors ordered darkest to lightest.
    """
    rgb = require_color(base_color)[:3]
    if not (2 <= steps <= 16):
        raise InputError("steps must be between 2 and 16")
    if not (0 <= lightness_range <= 1):
        raise InputError("lightness_range must be between 0 and 1")

    r, g, b = (c / 255 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    ramp = []
    mid = (steps - 1) / 2
    for i in range(steps):
        # t in [-0.5, 0.5]: negative = shadow side, positive = highlight side
        t = (i - mid) / (steps - 1) if steps > 1 else 0
        nh = (h - t * (hue_shift_degrees / 360)) % 1.0
        nl = min(1.0, max(0.0, l + t * lightness_range))
        # Shadows slightly more saturated, highlights slightly less
        ns = min(1.0, max(0.0, s - t * 0.15))
        nr, ng, nb = colorsys.hls_to_rgb(nh, nl, ns)
        ramp.append("#{:02X}{:02X}{:02X}".format(
            round(nr * 255), round(ng * 255), round(nb * 255)))
    return json.dumps(ramp)


@mcp.tool()
async def quantize_to_palette(
    filename: str,
    layer_name: str = "",
    start_frame: int = 1,
    end_frame: int = 0,
) -> str:
    """Snap every pixel to the nearest color in the sprite's palette.

    Walks the chosen cels and replaces each opaque pixel with the
    closest palette color (RGB distance). Run after apply_palette_preset
    or set_palette to make existing art conform to the palette.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to quantize (empty = every layer, including those inside groups)
        start_frame: First frame to process (default 1)
        end_frame: Last frame to process (default 0 = last frame)
    """
    require_file(filename)

    result = await call("palette.quantize", filename, layer=layer_name or None, first=start_frame, last=end_frame)
    return f"Quantized {result['count']} pixels to the palette in {filename}"


@mcp.tool()
async def set_color_mode(filename: str, mode: str) -> str:
    """Convert the sprite's color mode.

    Args:
        filename: Aseprite file to modify
        mode: "rgb", "grayscale", or "indexed"
    """
    require_file(filename)
    if mode.lower() not in ("rgb", "grayscale", "indexed"):
        raise InputError("mode must be 'rgb', 'grayscale', or 'indexed'")

    await call("palette.set_color_mode", filename, mode=mode.lower())
    return f"Color mode set to {mode} in {filename}"
