import glob
import os
from ..core.commands import lua_escape, run_script, run_cli
from ..core.boundary import require_file, require_safe_path
from ..core.errors import AsepriteError, InputError
from ..core.lua import FIND_LAYER, NORMALIZE_CEL
from .. import mcp

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
    
    # For animated exports
    if format == "gif":
        args = ["--batch", filename, "--save-as", output_filename]
        await run_cli(args)
    else:
        # For still image exports
        args = ["--batch", filename, "--save-as", output_filename]
        await run_cli(args)

    # Aseprite exits 0 even when it cannot write the requested format
    # (e.g. format="json"). Confirm a file actually appeared. A multi-frame
    # sprite saved to a still format produces frame-numbered siblings
    # (out1.png, out2.png, ...) instead of the exact name, so accept those
    # too — same convention as export_frame.
    base, ext = os.path.splitext(output_filename)
    if not os.path.exists(output_filename) and not glob.glob(f"{base}*{ext}"):
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

    safe_path = lua_escape(output_filename.replace("\\", "/"))
    script = f"""
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    spr:saveAs("{safe_path}")
    print("OK")
    """

    await run_script(script, filename)
    if not os.path.exists(output_filename):
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

    f0 = frame_index - 1  # CLI --frame-range is 0-based
    args = [
        "--batch", filename,
        "--frame-range", f"{f0},{f0}",
        "--scale", str(scale),
        "--save-as", output_filename,
    ]
    await run_cli(args)

    # With multi-frame sprites Aseprite may append the frame number to
    # the filename; rename the produced file when that happens.
    if not os.path.exists(output_filename):
        base, ext = os.path.splitext(output_filename)
        candidates = sorted(glob.glob(f"{base}*{ext}"))
        if candidates:
            os.replace(candidates[0], output_filename)
        else:
            raise AsepriteError(f"Export reported success but {output_filename} was not created")
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

    args = ["--batch"]
    if tag_name:
        # Frame filters only apply to --sheet when they appear before
        # the input file; resolve the tag to a 0-based --frame-range so
        # missing tags produce a clear error.
        safe_tag = lua_escape(tag_name)
        script = f"""
        local spr = app.activeSprite
        if not spr then print("ERROR:No active sprite") return end
        for _, tag in ipairs(spr.tags) do
            if tag.name == "{safe_tag}" then
                print("RANGE:" .. (tag.fromFrame.frameNumber - 1) .. "," .. (tag.toFrame.frameNumber - 1))
                return
            end
        end
        print("ERROR:Tag not found")
        """
        out = await run_script(script, filename)
        frame_range = next(
            (line[len("RANGE:"):] for line in out.splitlines() if line.startswith("RANGE:")),
            None,
        )
        if frame_range is None:
            raise AsepriteError("Failed to resolve tag: no range returned")
        args += ["--frame-range", frame_range]
    args.append(filename)
    if scale > 1:
        args += ["--scale", str(scale)]
    args += ["--sheet-type", sheet_type]
    if padding > 0:
        args += ["--shape-padding", str(padding)]
    if data_filename:
        require_safe_path(data_filename)
        args += ["--data", data_filename, "--format", data_format]
        if list_tags:
            args.append("--list-tags")
    args += ["--sheet", output_filename]

    await run_cli(args)
    if not os.path.exists(output_filename):
        raise AsepriteError("Aseprite exited 0 but wrote no sheet file")
    if data_filename and not os.path.exists(data_filename):
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

    args = ["--batch"]
    if include_hidden:
        args.append("--all-layers")
    args += [
        "--split-layers", filename,
        "--save-as", os.path.join(output_directory, "{layer}.png"),
    ]
    await run_cli(args)
    produced = sorted(
        os.path.basename(p) for p in glob.glob(os.path.join(output_directory, "*.png"))
    )
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
    # exist, so a produced file is not proof the tag was honoured. Validate
    # the tag up front — same approach as export_spritesheet.
    safe_tag = lua_escape(tag_name)
    check = f"""
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end
    for _, tag in ipairs(spr.tags) do
        if tag.name == "{safe_tag}" then print("OK") return end
    end
    print("ERROR:Tag not found")
    """
    await run_script(check, filename)

    args = ["--batch", filename, "--tag", tag_name]
    if scale > 1:
        args += ["--scale", str(scale)]
    args += ["--save-as", output_filename]
    await run_cli(args)
    # A multi-frame tag saved to a still format produces frame-numbered
    # siblings instead of the exact name — accept those, same convention
    # as export_sprite/export_frame.
    base, ext = os.path.splitext(output_filename)
    if not os.path.exists(output_filename) and not glob.glob(f"{base}*{ext}"):
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

    safe_layer = lua_escape(layer_name)
    safe_image = lua_escape(os.path.abspath(image_path).replace("\\", "/"))
    script = f"""
    {FIND_LAYER}
    {NORMALIZE_CEL}
    local spr = app.activeSprite
    if not spr then print("ERROR:No active sprite") return end

    local idx = {frame_index}
    if idx < 1 or idx > #spr.frames then print("ERROR:Frame index out of range") return end

    local src = Image{{ fromFile = "{safe_image}" }}
    if not src then print("ERROR:Could not load image") return end

    local target = find_layer(spr, "{safe_layer}")
    app.transaction(function()
        if not target then
            target = spr:newLayer()
            target.name = "{safe_layer}"
        end
        local cel = normalize_cel(spr, target, spr.frames[idx], true)
        cel.image:drawImage(src, Point({x}, {y}))
    end)

    spr:saveAs(spr.filename)
    print("OK")
    """

    await run_script(script, filename)
    return f"Image {image_path} imported onto '{layer_name}' frame {frame_index} in {filename}"
