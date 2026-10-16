import json

from ..core.commands import call
from ..core.boundary import require_file
from ..core.errors import InputError
from .. import mcp

# Must match EASINGS in lua/ops/animation.lua.
_EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out", "smoothstep")
_EASING_ERROR = "Unsupported easing (linear, ease_in, ease_out, ease_in_out, smoothstep)"

# Tool-facing direction name -> Aseprite's AniDir constant.
_DIRECTIONS = {
    "forward": "FORWARD",
    "reverse": "REVERSE",
    "pingpong": "PING_PONG",
    "pingpong_reverse": "PING_PONG_REVERSE",
}


def _easing(name: str) -> str:
    easing = (name or "smoothstep").lower().strip()
    if easing not in _EASINGS:
        raise InputError(_EASING_ERROR)
    return easing


@mcp.tool()
async def add_frames(filename: str, count: int, duration_ms: int | None = None) -> str:
    """Add multiple frames to a sprite and optionally set their duration.

    Args:
        filename: Name of the Aseprite file to modify
        count: Number of frames to add
        duration_ms: Optional duration for each new frame in milliseconds
    """
    require_file(filename)
    if count < 1:
        raise InputError("Count must be >= 1")

    duration = duration_ms if duration_ms is not None and duration_ms > 0 else None
    await call("animation.add_frames", filename, count=count, duration_ms=duration)
    return f"Added {count} frames to {filename}"


@mcp.tool()
async def set_frame_duration_all(filename: str, duration_ms: int) -> str:
    """Set the duration of all frames in milliseconds.

    Args:
        filename: Name of the Aseprite file to modify
        duration_ms: Duration in milliseconds
    """
    require_file(filename)
    if duration_ms <= 0:
        raise InputError("Duration must be > 0")

    await call("animation.set_frame_duration_all", filename, duration_ms=duration_ms)
    return f"Set duration of all frames to {duration_ms}ms in {filename}"


@mcp.tool()
async def set_layer_visibility(filename: str, layer_name: str, visible: bool = True) -> str:
    """Set layer visibility by name.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        visible: Whether the layer should be visible
    """
    require_file(filename)

    await call("animation.set_layer_visibility", filename, name=layer_name, visible=visible)
    return f"Layer '{layer_name}' visibility set to {visible} in {filename}"


@mcp.tool()
async def set_layer_opacity(filename: str, layer_name: str, opacity: int) -> str:
    """Set layer opacity by name (0-255).

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        opacity: Opacity value 0-255
    """
    require_file(filename)
    if opacity < 0 or opacity > 255:
        raise InputError("Opacity must be between 0 and 255")

    await call("animation.set_layer_opacity", filename, name=layer_name, opacity=opacity)
    return f"Layer '{layer_name}' opacity set to {opacity} in {filename}"


@mcp.tool()
async def get_sprite_info(filename: str) -> str:
    """Return sprite info as JSON string (size, color mode, frame durations, layers, tags).

    Args:
        filename: Name of the Aseprite file to inspect
    """
    require_file(filename)

    info = await call("animation.sprite_info", filename)
    # Lua drops nil fields; top-level layers report parent null.
    info["layers"] = [{**layer, "parent": layer.get("parent")} for layer in info["layers"]]
    keys = ("width", "height", "color_mode", "frames", "durations_ms", "layers", "tags")
    return json.dumps({key: info[key] for key in keys})


@mcp.tool()
async def duplicate_frame_range(filename: str, start_frame: int, end_frame: int, times: int = 1) -> str:
    """Duplicate a frame range and append copies to the end.

    Args:
        filename: Name of the Aseprite file to modify
        start_frame: Starting frame index (1-based)
        end_frame: Ending frame index (1-based, inclusive)
        times: Number of times to append the range (default: 1)
    """
    require_file(filename)
    if times < 1:
        raise InputError("Times must be >= 1")

    await call("animation.duplicate_frame_range", filename, first=start_frame, last=end_frame, times=times)
    return f"Duplicated frames {start_frame}-{end_frame} (x{times}) in {filename}"


@mcp.tool()
async def set_cel_position(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    create_if_missing: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Set a cel's position in a specific layer and frame.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        frame_index: Frame index starting at 1
        x: X position in pixels
        y: Y position in pixels
        create_if_missing: Create the cel if it does not exist
        source_frame_index: Optional frame to copy the cel image from
    """
    require_file(filename)

    await call("animation.set_cel_position", filename, name=layer_name, frame=frame_index, x=x, y=y,
               create_if_missing=create_if_missing, source_frame=source_frame_index)
    return f"Cel position set to ({x}, {y}) on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def tween_cel_positions(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    create_missing_cels: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Tween cel positions linearly across a frame range.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        start_frame: Starting frame index (1-based)
        end_frame: Ending frame index (1-based, inclusive)
        start_x: Starting X position in pixels
        start_y: Starting Y position in pixels
        end_x: Ending X position in pixels
        end_y: Ending Y position in pixels
        create_missing_cels: Create missing cels during tween
        source_frame_index: Optional frame to copy the cel image from
    """
    require_file(filename)

    await call("animation.tween_position", filename, name=layer_name, first=start_frame, last=end_frame,
               start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y, easing="linear",
               create_missing=create_missing_cels, source_frame=source_frame_index)
    return f"Tweened cel positions on '{layer_name}' frames {start_frame}-{end_frame} in {filename}"


@mcp.tool()
async def offset_cel_positions(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    dx: int,
    dy: int
) -> str:
    """Offset cel positions by a delta across a frame range.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        start_frame: Starting frame index (1-based)
        end_frame: Ending frame index (1-based, inclusive)
        dx: X delta in pixels
        dy: Y delta in pixels
    """
    require_file(filename)

    await call("animation.offset_cel_positions", filename, name=layer_name, first=start_frame, last=end_frame,
               dx=dx, dy=dy)
    return f"Offset cel positions by ({dx}, {dy}) on '{layer_name}' frames {start_frame}-{end_frame} in {filename}"


@mcp.tool()
async def create_cel(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int = 0,
    y: int = 0
) -> str:
    """Create an empty cel on a layer/frame.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        frame_index: Frame index starting at 1
        x: X position in pixels
        y: Y position in pixels
    """
    require_file(filename)

    await call("animation.create_cel", filename, name=layer_name, frame=frame_index, x=x, y=y)
    return f"Cel created on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def clear_cel(filename: str, layer_name: str, frame_index: int) -> str:
    """Delete a cel on a layer/frame."""
    require_file(filename)

    await call("animation.clear_cel", filename, name=layer_name, frame=frame_index)
    return f"Cel cleared on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def copy_cel(
    filename: str,
    layer_name: str,
    source_frame: int,
    target_frame: int,
    replace: bool = True
) -> str:
    """Copy a cel from one frame to another."""
    require_file(filename)

    await call("animation.copy_cel", filename, name=layer_name, source=source_frame, target=target_frame,
               replace=replace)
    return f"Cel copied on '{layer_name}' from frame {source_frame} to {target_frame} in {filename}"


@mcp.tool()
async def copy_frame(
    filename: str,
    source_frame: int,
    target_frame: int | None = None,
    overwrite: bool = True
) -> str:
    """Copy all cels from a source frame to a target frame (or append)."""
    require_file(filename)

    await call("animation.copy_frame", filename, source=source_frame, target=target_frame, overwrite=overwrite)
    if target_frame is None:
        return f"Frame {source_frame} copied to new frame in {filename}"
    return f"Frame {source_frame} copied to frame {target_frame} in {filename}"


@mcp.tool()
async def propagate_frame_to_range(
    filename: str,
    source_frame: int,
    start_frame: int,
    end_frame: int,
    overwrite: bool = True
) -> str:
    """Copy all layers from a source frame to a range of frames.

    Args:
        filename: Name of the Aseprite file to modify
        source_frame: Frame index to copy from (1-based)
        start_frame: Start frame index (1-based)
        end_frame: End frame index (1-based, inclusive)
        overwrite: Whether to overwrite existing cels (default: True)
    """
    require_file(filename)

    await call("animation.propagate_frame_to_range", filename, source=source_frame, first=start_frame,
               last=end_frame, overwrite=overwrite)
    return (
        f"Propagated frame {source_frame} to frames {start_frame}-{end_frame} "
        f"in {filename}"
    )


@mcp.tool()
async def set_tag(
    filename: str,
    name: str,
    from_frame: int,
    to_frame: int,
    direction: str = "forward"
) -> str:
    """Create or update an animation tag on the sprite.

    direction: forward | reverse | pingpong | pingpong_reverse
    """
    require_file(filename)
    if direction not in _DIRECTIONS:
        raise InputError(f"Unsupported direction '{direction}' (forward, reverse, pingpong, pingpong_reverse)")

    await call("animation.set_tag", filename, name=name, first=from_frame, last=to_frame,
               direction=_DIRECTIONS[direction])
    return f"Tag '{name}' set to frames {from_frame}-{to_frame} (direction={direction}) in {filename}"


@mcp.tool()
async def set_onion_skin(
    filename: str,
    enabled: bool = True,
    before: int = 2,
    after: int = 2,
    opacity: int = 128
) -> str:
    """Configure onion skin settings for Aseprite."""
    require_file(filename)
    if before < 0 or after < 0:
        raise InputError("Before/after must be >= 0")
    if opacity < 0 or opacity > 255:
        raise InputError("Opacity must be between 0 and 255")

    return (
        "Onion skin settings are UI-only in batch mode; no changes applied "
        f"(enabled={enabled}, before={before}, after={after}, opacity={opacity})"
    )


@mcp.tool()
async def propagate_cels(
    filename: str,
    layer_names: list[str],
    source_frame: int,
    start_frame: int,
    end_frame: int,
    replace: bool = True
) -> str:
    """Copy cels from a source frame to a range of frames for specific layers.

    Args:
        filename: Name of the Aseprite file to modify
        layer_names: List of layer names to copy
        source_frame: Frame index to copy from (1-based)
        start_frame: Start frame index (1-based)
        end_frame: End frame index (1-based, inclusive)
        replace: Whether to overwrite existing cels (default: True)
    """
    require_file(filename)
    if not layer_names:
        raise InputError("Layer names list cannot be empty")

    await call("animation.propagate_cels", filename, names=layer_names, source=source_frame, first=start_frame,
               last=end_frame, replace=replace)
    return (
        f"Propagated cels from frame {source_frame} to frames {start_frame}-{end_frame} "
        f"for layers {', '.join(layer_names)} in {filename}"
    )


@mcp.tool()
async def tween_cel_positions_eased(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    easing: str = "smoothstep",
    create_missing_cels: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Tween cel positions with easing across a frame range."""
    require_file(filename)
    easing = _easing(easing)

    await call("animation.tween_position", filename, name=layer_name, first=start_frame, last=end_frame,
               start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y, easing=easing,
               create_missing=create_missing_cels, source_frame=source_frame_index)
    return (
        f"Tweened cel positions ({easing}) on '{layer_name}' frames {start_frame}-{end_frame} "
        f"in {filename}"
    )


@mcp.tool()
async def oscillate_cel_positions(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    amplitude_x: int = 0,
    amplitude_y: int = 0,
    cycles: float = 1.0,
    phase_deg: float = 0.0,
    create_missing_cels: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Oscillate cel positions across a frame range using a sine wave."""
    require_file(filename)

    await call("animation.oscillate", filename, name=layer_name, first=start_frame, last=end_frame,
               amplitude_x=amplitude_x, amplitude_y=amplitude_y, cycles=cycles, phase_deg=phase_deg,
               create_missing=create_missing_cels, source_frame=source_frame_index)
    return (
        f"Oscillated cel positions on '{layer_name}' frames {start_frame}-{end_frame} "
        f"in {filename}"
    )


@mcp.tool()
async def tween_cel_opacity_eased(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    start_opacity: int,
    end_opacity: int,
    easing: str = "smoothstep",
    create_missing_cels: bool = False,
    source_frame_index: int | None = None
) -> str:
    """Tween cel opacity with easing across a frame range."""
    require_file(filename)
    if start_opacity < 0 or start_opacity > 255 or end_opacity < 0 or end_opacity > 255:
        raise InputError("Opacity must be between 0 and 255")
    easing = _easing(easing)

    await call("animation.tween_opacity", filename, name=layer_name, first=start_frame, last=end_frame,
               start_opacity=start_opacity, end_opacity=end_opacity, easing=easing,
               create_missing=create_missing_cels, source_frame=source_frame_index)
    return (
        f"Tweened cel opacity ({easing}) on '{layer_name}' frames {start_frame}-{end_frame} "
        f"in {filename}"
    )


@mcp.tool()
async def tween_cel_scale_eased(
    filename: str,
    layer_name: str,
    start_frame: int,
    end_frame: int,
    start_scale: float,
    end_scale: float,
    easing: str = "smoothstep",
    anchor: str = "center",
    replace: bool = True,
    create_missing_cels: bool = True,
    source_frame_index: int | None = None
) -> str:
    """Tween cel scale with easing across a frame range."""
    require_file(filename)
    if start_scale <= 0 or end_scale <= 0:
        raise InputError("Scale must be > 0")
    easing = _easing(easing)
    anchor = (anchor or "center").lower().strip()
    if anchor not in {"center", "topleft"}:
        raise InputError("Unsupported anchor (center, topleft)")

    await call("animation.tween_scale", filename, name=layer_name, first=start_frame, last=end_frame,
               start_scale=start_scale, end_scale=end_scale, easing=easing, anchor=anchor, replace=replace,
               create_missing=create_missing_cels, source_frame=source_frame_index)
    return (
        f"Tweened cel scale ({easing}) on '{layer_name}' frames {start_frame}-{end_frame} "
        f"in {filename}"
    )


@mcp.tool()
async def delete_frame(filename: str, frame_index: int) -> str:
    """Delete a frame by index.

    Args:
        filename: Aseprite file to modify
        frame_index: Frame index starting at 1
    """
    require_file(filename)

    await call("animation.delete_frame", filename, frame=frame_index)
    return f"Frame {frame_index} deleted from {filename}"


@mcp.tool()
async def delete_tag(filename: str, name: str) -> str:
    """Delete an animation tag by name.

    Args:
        filename: Aseprite file to modify
        name: Tag name to delete
    """
    require_file(filename)

    await call("animation.delete_tag", filename, name=name)
    return f"Tag '{name}' deleted from {filename}"


@mcp.tool()
async def set_cel_opacity(
    filename: str,
    layer_name: str,
    frame_index: int,
    opacity: int,
) -> str:
    """Set the opacity of a single cel (0-255).

    Args:
        filename: Aseprite file to modify
        layer_name: Layer containing the cel
        frame_index: Frame index starting at 1
        opacity: Opacity 0 (transparent) to 255 (opaque)
    """
    require_file(filename)
    if not (0 <= opacity <= 255):
        raise InputError("Opacity must be between 0 and 255")

    await call("animation.set_cel_opacity", filename, name=layer_name, frame=frame_index, opacity=opacity)
    return f"Cel opacity set to {opacity} on '{layer_name}' frame {frame_index} in {filename}"
