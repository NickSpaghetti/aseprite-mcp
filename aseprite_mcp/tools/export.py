import glob
import os

from ..core.commands import call, run_cli
from ..core.boundary import require_file, require_safe_path
from ..core.errors import AsepriteError, InputError
from .. import mcp


def _pattern(path: str, wildcard: str = "") -> str:
    """A glob for `path` (plus an optional wildcard before its extension) that
    treats every character of the path literally."""
    base, ext = os.path.splitext(path)
    return glob.escape(base) + wildcard + glob.escape(ext)


def _snapshot(pattern: str) -> dict[str, int]:
    return {p: os.stat(p).st_mtime_ns for p in glob.glob(pattern)}


def _written(before: dict[str, int], pattern: str) -> list[str]:
    """Files matching `pattern` that are new or changed since `before`.

    Aseprite exits 0 even when it writes nothing, and a file left over from an
    earlier export is not proof this one worked.
    """
    return sorted(p for p, mtime in _snapshot(pattern).items() if before.get(p) != mtime)


async def _tag_range(filename: str, tag_name: str) -> tuple[int, int]:
    result = await call("export.tag_range", filename, name=tag_name)
    return result["first"], result["last"]


@mcp.tool()
async def export_sprite(filename: str, output_filename: str, format: str = "png") -> str:
    """Export the Aseprite file to another format.

    Args:
        filename: Name of the Aseprite file to export
        output_filename: Name of the output file
        format: Output format (default: "png", can be "png", "gif", "jpg", etc.)
    """
    require_file(filename)

    # Make sure format is lowercase
    format = format.lower()

    # Ensure output filename has the correct extension
    if not output_filename.lower().endswith(f".{format}"):
        output_filename = f"{output_filename}.{format}"
    require_safe_path(output_filename)

    # A multi-frame sprite saved to a still format produces frame-numbered
    # siblings (out1.png, out2.png, ...) instead of the exact name, so those count.
    pattern = _pattern(output_filename, "*")
    before = _snapshot(pattern)
    await run_cli(["--batch", filename, "--save-as", output_filename])
    if not _written(before, pattern):
        raise AsepriteError("Aseprite exited 0 but wrote no file (the format may not be writable via --save-as)")

    return f"Sprite exported successfully to {output_filename}"


@mcp.tool()
async def copy_sprite(filename: str, output_filename: str, overwrite: bool = False) -> str:
    """Copy a sprite to a new Aseprite file.

    Args:
        filename: Name of the Aseprite file to copy
        output_filename: Name of the output .aseprite file
        overwrite: Whether to overwrite if output exists
    """
    require_file(filename)

    if not output_filename.lower().endswith(".aseprite"):
        output_filename = f"{output_filename}.aseprite"

    require_safe_path(output_filename)

    if os.path.exists(output_filename) and not overwrite:
        raise InputError(f"Output file {output_filename} already exists")

    before = _snapshot(_pattern(output_filename))
    await call("export.copy", filename, output=os.path.abspath(output_filename))
    if not _written(before, _pattern(output_filename)):
        raise AsepriteError("Aseprite exited 0 but wrote no file")
    return f"Sprite copied to {output_filename}"


@mcp.tool()
async def export_frame(
    filename: str,
    frame_index: int,
    output_filename: str,
    scale: int = 1,
) -> str:
    """Export a single frame as a PNG, optionally scaled up.

    Use this for visual feedback while drawing: export at scale 8-10 and
    open the PNG to inspect the result, then keep iterating.

    Args:
        filename: Aseprite file to export
        frame_index: Frame index starting at 1
        output_filename: Output PNG path
        scale: Integer nearest-neighbor scale factor (default 1)
    """
    require_file(filename)
    if scale < 1 or scale > 64:
        raise InputError("scale must be between 1 and 64")
    require_safe_path(output_filename)
    if not output_filename.lower().endswith(".png"):
        output_filename = f"{output_filename}.png"

    pattern = _pattern(output_filename, "*")
    before = _snapshot(pattern)
    f0 = frame_index - 1  # CLI --frame-range is 0-based
    await run_cli([
        "--batch", filename,
        "--frame-range", f"{f0},{f0}",
        "--scale", str(scale),
        "--save-as", output_filename,
    ])

    # With multi-frame sprites Aseprite may append the frame number to
    # the filename; rename the produced file when that happens.
    written = _written(before, pattern)
    if output_filename not in written:
        if not written:
            raise AsepriteError(f"Export reported success but {output_filename} was not created")
        os.replace(written[0], output_filename)
    return f"Frame {frame_index} exported to {output_filename} at {scale}x"


@mcp.tool()
async def export_spritesheet(
    filename: str,
    output_filename: str,
    sheet_type: str = "horizontal",
    data_filename: str = "",
    scale: int = 1,
    padding: int = 0,
    tag_name: str = "",
    data_format: str = "json-array",
    list_tags: bool = False,
) -> str:
    """Export frames as a sprite sheet, optionally with a JSON data file.

    Args:
        filename: Aseprite file to export
        output_filename: Output sheet image path (PNG)
        sheet_type: Layout: "horizontal", "vertical", "rows", "columns", or "packed"
        data_filename: Optional path for a JSON metadata file
        scale: Integer scale factor applied before packing (default 1)
        padding: Padding in pixels between frames (default 0)
        tag_name: Only include frames of this animation tag (default: all frames)
        data_format: JSON format for the data file: "json-array" (default) or "json-hash"
        list_tags: Include animation tag metadata in the JSON data file (default: False)
    """
    require_file(filename)
    if sheet_type not in ("horizontal", "vertical", "rows", "columns", "packed"):
        raise InputError("sheet_type must be one of: horizontal, vertical, rows, columns, packed")
    if scale < 1 or scale > 64:
        raise InputError("scale must be between 1 and 64")
    if padding < 0:
        raise InputError("padding must be >= 0")
    if data_format not in ("json-array", "json-hash"):
        raise InputError("data_format must be 'json-array' or 'json-hash'")
    require_safe_path(output_filename)
    if not output_filename.lower().endswith(".png"):
        output_filename = f"{output_filename}.png"
    if data_filename:
        require_safe_path(data_filename)

    args = ["--batch"]
    if tag_name:
        # Frame filters only apply to --sheet when they appear before the
        # input file; resolve the tag to a 0-based --frame-range so a missing
        # tag fails clearly instead of exporting every frame.
        first, last = await _tag_range(filename, tag_name)
        args += ["--frame-range", f"{first - 1},{last - 1}"]
    args.append(filename)
    if scale > 1:
        args += ["--scale", str(scale)]
    args += ["--sheet-type", sheet_type]
    if padding > 0:
        args += ["--shape-padding", str(padding)]
    if data_filename:
        args += ["--data", data_filename, "--format", data_format]
        if list_tags:
            args.append("--list-tags")
    args += ["--sheet", output_filename]

    sheet_before = _snapshot(_pattern(output_filename))
    data_before = _snapshot(_pattern(data_filename)) if data_filename else {}
    await run_cli(args)
    if not _written(sheet_before, _pattern(output_filename)):
        raise AsepriteError("Aseprite exited 0 but wrote no sheet file")
    if data_filename and not _written(data_before, _pattern(data_filename)):
        raise AsepriteError("Aseprite exited 0 but wrote no data file")
    msg = f"Sprite sheet exported to {output_filename} ({sheet_type})"
    if data_filename:
        msg += f" with data file {data_filename}"
    return msg


@mcp.tool()
async def export_layers(
    filename: str,
    output_directory: str,
    include_hidden: bool = False,
) -> str:
    """Export each layer as its own PNG file named <layer>.png.

    Args:
        filename: Aseprite file to export
        output_directory: Directory for the per-layer PNGs (created if missing)
        include_hidden: Also export hidden layers (default False)
    """
    require_file(filename)
    require_safe_path(output_directory)
    os.makedirs(output_directory, exist_ok=True)

    pattern = os.path.join(glob.escape(output_directory), "*.png")
    before = _snapshot(pattern)
    args = ["--batch"]
    if include_hidden:
        args.append("--all-layers")
    args += [
        "--split-layers", filename,
        "--save-as", os.path.join(output_directory, "{layer}.png"),
    ]
    await run_cli(args)
    produced = [os.path.basename(p) for p in _written(before, pattern)]
    if not produced:
        raise AsepriteError("Failed to export layers: Aseprite exited 0 but wrote no PNG files")
    return f"Layers exported to {output_directory}: {', '.join(produced)}"


@mcp.tool()
async def export_tag(
    filename: str,
    tag_name: str,
    output_filename: str,
    scale: int = 1,
) -> str:
    """Export the frames of an animation tag as a GIF or PNG sequence.

    Args:
        filename: Aseprite file to export
        tag_name: Animation tag to export
        output_filename: Output path; .gif gives an animation, .png a sequence
        scale: Integer scale factor (default 1)
    """
    require_file(filename)
    if scale < 1 or scale > 64:
        raise InputError("scale must be between 1 and 64")
    require_safe_path(output_filename)

    # --tag silently exports *all* frames (exit 0) when the tag does not
    # exist, so a produced file is not proof the tag was honoured.
    await _tag_range(filename, tag_name)

    args = ["--batch", filename, "--tag", tag_name]
    if scale > 1:
        args += ["--scale", str(scale)]
    args += ["--save-as", output_filename]
    # A multi-frame tag saved to a still format produces frame-numbered
    # siblings instead of the exact name; those count.
    pattern = _pattern(output_filename, "*")
    before = _snapshot(pattern)
    await run_cli(args)
    if not _written(before, pattern):
        raise AsepriteError("Aseprite exited 0 but wrote no file")
    return f"Tag '{tag_name}' exported to {output_filename}"


@mcp.tool()
async def import_image_as_layer(
    filename: str,
    image_path: str,
    layer_name: str,
    frame_index: int = 1,
    x: int = 0,
    y: int = 0,
) -> str:
    """Import an image file (PNG, etc.) into a layer of the sprite.

    Useful for bringing in reference images or composing pre-made parts.
    The layer is created if it does not exist. Works best when the sprite
    is in RGB color mode.

    Args:
        filename: Aseprite file to modify
        image_path: Image file to import
        layer_name: Layer to place the image on
        frame_index: Frame index starting at 1 (default 1)
        x: X position for the image's top-left corner (default 0)
        y: Y position for the image's top-left corner (default 0)
    """
    require_file(filename)
    if not os.path.exists(image_path):
        raise InputError(f"Image {image_path} not found")

    await call("export.import_image", filename, path=os.path.abspath(image_path), layer=layer_name,
               frame=frame_index, x=x, y=y)
    return f"Image {image_path} imported onto '{layer_name}' frame {frame_index} in {filename}"
