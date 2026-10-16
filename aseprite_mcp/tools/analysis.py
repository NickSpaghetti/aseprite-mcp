import json
import os

from ..core.commands import call
from ..core.boundary import require_file, require_safe_path
from ..core.errors import InputError
from .. import mcp


@mcp.tool()
async def render_onion_skin(
    filename: str,
    frame_index: int,
    output_filename: str,
    before: int = 1,
    after: int = 1,
    scale: int = 4,
    ghost_opacity: int = 100,
) -> str:
    """Render a frame with neighboring frames as translucent onion-skin ghosts.

    Produces a PNG of the given frame composited over ghosted copies of
    the surrounding frames — the batch-mode equivalent of Aseprite's
    onion skinning. Essential for checking motion continuity while
    animating: export it, open the PNG, and verify the in-between
    positions line up.

    Args:
        filename: Aseprite file to read
        frame_index: Frame to render, starting at 1
        output_filename: Output PNG path
        before: Number of previous frames to ghost (default 1)
        after: Number of following frames to ghost (default 1)
        scale: Integer nearest-neighbor scale factor (default 4)
        ghost_opacity: Opacity of ghost frames, 0-255 (default 100)
    """
    require_file(filename)
    if scale < 1 or scale > 64:
        raise InputError("scale must be between 1 and 64")
    if not (0 <= ghost_opacity <= 255):
        raise InputError("ghost_opacity must be between 0 and 255")
    if before < 0 or after < 0:
        raise InputError("before and after must be >= 0")
    require_safe_path(output_filename)
    if not output_filename.lower().endswith(".png"):
        output_filename = f"{output_filename}.png"

    await call("analysis.onion_skin", filename, frame=frame_index, before=before, after=after, scale=scale,
               ghost_opacity=ghost_opacity, output=os.path.abspath(output_filename))
    return (
        f"Onion-skin render of frame {frame_index} "
        f"(-{before}/+{after} ghosts) saved to {output_filename} at {scale}x"
    )


@mcp.tool()
async def compare_frames(filename: str, frame_a: int, frame_b: int) -> str:
    """Compare two frames and report how much they differ.

    Composites each frame's visible layers (non-destructively; hidden
    layers are left out) and diffs the two frames pixel by pixel. Use while animating to confirm a frame actually
    changed, or that it did not change too much.

    Args:
        filename: Aseprite file to read
        frame_a: First frame index, starting at 1
        frame_b: Second frame index, starting at 1

    Returns:
        JSON with changed pixel count, total pixels, percent changed,
        and the bounding box of the changed region.
    """
    require_file(filename)

    diff = await call("analysis.compare", filename, frame_a=frame_a, frame_b=frame_b)
    total = diff["total"]
    result = {
        "frame_a": frame_a,
        "frame_b": frame_b,
        "changed_pixels": diff["changed"],
        "total_pixels": total,
        "percent_changed": round(diff["changed"] / total * 100, 2) if total else 0,
    }
    if "bounds" in diff:
        result["changed_bounds"] = {k: diff["bounds"][k] for k in ("x", "y", "width", "height")}
    return json.dumps(result)


@mcp.tool()
async def get_color_stats(filename: str, frame_index: int = 1, top: int = 16) -> str:
    """Report the colors used in a frame and how often each appears.

    Composites the frame's visible layers (non-destructively; hidden
    layers are left out) and histograms it.
    Use to check palette discipline: too many near-duplicate colors is
    a common pixel-art mistake.

    Args:
        filename: Aseprite file to read
        frame_index: Frame to analyze, starting at 1 (default 1)
        top: How many of the most-used colors to list (default 16)

    Returns:
        JSON with unique color count, opaque pixel count, and the top
        colors with usage counts.
    """
    require_file(filename)
    if top < 1:
        raise InputError("top must be >= 1")

    stats = await call("analysis.color_stats", filename, frame=frame_index)
    colors = sorted(stats["colors"] or [], key=lambda c: (-c["count"], c["color"]))
    return json.dumps({
        "frame": frame_index,
        "unique_colors": len(colors),
        "opaque_pixels": stats["opaque"],
        "top_colors": [{"color": c["color"], "count": c["count"]} for c in colors[:top]],
    })
