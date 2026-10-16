import json
from typing import List

from ..core.commands import call
from ..core.boundary import require_file
from ..core.errors import InputError
from .. import mcp


def _parse_ranges(entries: List[str] | None) -> list:
    """["layer:1-8,17-24", ...] -> [[layer, [[1, 8], [17, 24]]], ...].

    The layer name is everything before the last ':', so names may contain ':'.
    """
    parsed = []
    for entry in entries or []:
        if not isinstance(entry, str) or ":" not in entry:
            raise InputError(f"Frame range {entry!r} must look like 'layer:1-8,17-24'")
        name, spans_text = entry.rsplit(":", 1)
        if not name.strip():
            raise InputError(f"Frame range {entry!r} has no layer name")
        spans = []
        for span in spans_text.split(","):
            first, _, last = span.strip().partition("-")
            if not (first.isdigit() and last.isdigit()) or int(first) < 1 or int(last) < int(first):
                raise InputError(f"Frame range {entry!r}: {span.strip()!r} must be 'first-last' with 1 <= first <= last")
            spans.append([int(first), int(last)])
        parsed.append([name.strip(), spans])
    return parsed


def _parse_pairs(entries: List[str] | None) -> list:
    """["a,b", "c:d", ...] -> [[a, b], [c, d], ...]; split on the first ',' else the first ':'."""
    parsed = []
    for entry in entries or []:
        separator = "," if isinstance(entry, str) and "," in entry else ":"
        left, found, right = entry.partition(separator) if isinstance(entry, str) else ("", "", "")
        if not found or not left.strip() or not right.strip():
            raise InputError(f"Overlap pair {entry!r} must look like 'layerA,layerB'")
        parsed.append([left.strip(), right.strip()])
    return parsed


def _overlap_json(entry: dict) -> dict:
    out = {"frame": entry["frame"], "a": entry["a"], "b": entry["b"]}
    if "a_bounds" in entry:
        out["a_bounds"], out["b_bounds"] = entry["a_bounds"], entry["b_bounds"]
    return out


@mcp.tool()
async def ensure_layers_present(
    filename: str,
    layer_names: List[str],
    start_frame: int = 1,
    end_frame: int | None = None
) -> str:
    """Ensure cels exist for layers across a frame range."""
    require_file(filename)
    if not layer_names:
        raise InputError("Layer names list cannot be empty")

    await call("quality.ensure_layers", filename, names=layer_names, first=start_frame, last=end_frame)
    return (
        f"Ensured cels for layers {', '.join(layer_names)} "
        f"on frames {start_frame}-{end_frame or 'end'} in {filename}"
    )


@mcp.tool()
async def validate_scene(
    filename: str,
    required_layers: List[str],
    start_frame: int = 1,
    end_frame: int | None = None
) -> str:
    """Validate presence of layers and cels across a frame range.

    Returns JSON with missing layers and missing cels.
    """
    require_file(filename)
    if not required_layers:
        raise InputError("Required layers list cannot be empty")

    r = await call("quality.validate", filename, names=required_layers, first=start_frame, last=end_frame)
    return json.dumps({
        "frames": r["frames"],
        "range": {"start": r["first"], "end": r["last"]},
        "missing_layers": r["missing_layers"] or [],
        "missing_cels": [{"layer": c["layer"], "frame": c["frame"]} for c in r["missing_cels"] or []],
    })


@mcp.tool()
async def audit_animation(
    filename: str,
    start_frame: int = 1,
    end_frame: int | None = None,
    layer_names: List[str] | None = None,
    overlap_pairs: List[str] | None = None,
    layer_frame_ranges: List[str] | None = None,
    report_cels: bool = False,
    report_bounds: bool = False,
    max_overlaps: int = 200,
    max_out_of_range: int = 200
) -> str:
    """Audit animation frames for overlaps and out-of-range layer activity.

    overlap_pairs format: ["layerA,layerB", "layerC:layerD"]
    layer_frame_ranges format: ["layer:1-8,17-24", "clouds:1-12"]
    Returns JSON for AI consumption (summary, overlaps, out_of_range, optional cels).
    """
    require_file(filename)
    if start_frame < 1:
        raise InputError("Start frame must be >= 1")
    if end_frame is not None and end_frame < start_frame:
        raise InputError("End frame must be >= start frame")
    if max_overlaps < 0 or max_out_of_range < 0:
        raise InputError("Max limits must be >= 0")

    r = await call("quality.audit", filename, first=start_frame, last=end_frame, names=layer_names or None,
                   pairs=_parse_pairs(overlap_pairs), ranges=_parse_ranges(layer_frame_ranges),
                   report_cels=report_cels, report_bounds=report_bounds,
                   max_overlaps=max_overlaps, max_out_of_range=max_out_of_range)
    overlaps = [_overlap_json(o) for o in r["overlaps"] or []]
    out_of_range = [{"frame": o["frame"], "layer": o["layer"]} for o in r["out_of_range"] or []]
    result = {
        "frames": {"start": r["first"], "end": r["last"]},
        "summary": {
            "total_layers": r["total_layers"],
            "layers_checked": r["layers_checked"],
            "total_cels": r["total_cels"],
            "overlaps": len(overlaps),
            "overlaps_total": r["overlaps_total"],
            "overlaps_truncated": r["overlaps_truncated"],
            "out_of_range": len(out_of_range),
        },
        "overlaps": overlaps,
        "out_of_range": out_of_range,
    }
    if report_cels:
        cel_keys = ("layer", "x", "y", "w", "h")
        result["cels"] = [
            {"frame": f["frame"], "cels": [{k: c[k] for k in cel_keys if k in c} for c in f["cels"] or []]}
            for f in r.get("cels") or []
        ]
    return json.dumps(result)


@mcp.tool()
async def animation_sanitize(
    filename: str,
    start_frame: int = 1,
    end_frame: int | None = None,
    layer_names: List[str] | None = None,
    layer_order: List[str] | None = None,
    layer_frame_ranges: List[str] | None = None,
    ensure_layers: List[str] | None = None,
    overlap_pairs: List[str] | None = None,
    report_bounds: bool = False,
    max_overlaps: int = 200,
    ignore_full_canvas_overlaps: bool = True,
    out_of_range_action: str = "set_opacity_zero",
    out_of_range_opacity: int = 0,
    report_only: bool = False,
    include_stats: bool = True
) -> str:
    """Normalize animation consistency and optionally apply fixes.

    layer_frame_ranges format: ["layer:1-8,17-24", "clouds:1-12"]
    out_of_range_action: "set_opacity_zero", "delete_cels", "none"
    ignore_full_canvas_overlaps: skip overlap checks when a cel is full canvas
    Returns JSON for AI consumption (summary, layer_stats, alerts, overlaps).
    """
    require_file(filename)
    if start_frame < 1:
        raise InputError("Start frame must be >= 1")
    if end_frame is not None and end_frame < start_frame:
        raise InputError("End frame must be >= start frame")
    if max_overlaps < 0:
        raise InputError("max_overlaps must be >= 0")
    if out_of_range_action not in {"set_opacity_zero", "delete_cels", "none"}:
        raise InputError("Unsupported out_of_range_action")
    if out_of_range_opacity < 0 or out_of_range_opacity > 255:
        raise InputError("out_of_range_opacity must be 0-255")

    # A report never touches the file: it runs as a read op.
    op = "quality.sanitize_report" if report_only else "quality.sanitize"
    r = await call(op, filename, first=start_frame, last=end_frame, names=layer_names or None,
                   order=layer_order or None, ensure=ensure_layers or None,
                   ranges=_parse_ranges(layer_frame_ranges), pairs=_parse_pairs(overlap_pairs),
                   report_bounds=report_bounds, max_overlaps=max_overlaps,
                   ignore_full_canvas=ignore_full_canvas_overlaps, action=out_of_range_action,
                   opacity=out_of_range_opacity)
    stats = r["stats"] or []
    result = {
        "frames": {"start": r["first"], "end": r["last"]},
        "reordered": r["reordered"],
        "ensured": r["ensured"],
        "out_of_range": r["out_of_range"],
        "opacity_set": r["opacity_set"],
        "deleted": r["deleted"],
        "analysis": {
            "total_layers": r["total_layers"],
            "layers_checked": r["layers_checked"],
            "total_cels": r["total_cels"],
            "empty_frames": r["empty_frames"],
            "overlaps": r["overlaps"],
            "overlaps_total": r["overlaps"],
            "overlaps_truncated": r["overlaps_truncated"],
            "inactive_layers": [s["name"] for s in stats if s["frames_active"] == 0],
        },
    }
    if include_stats:
        result["layer_stats"] = {
            s["name"]: {"frames_active": s["frames_active"], "cel_count": s["cel_count"],
                        "full_canvas_cels": s["full_canvas_cels"], "bounds": s.get("bounds")}
            for s in stats
        }
    alerts = []
    if r["empty_frames"] > 0:
        alerts.append("empty_frames_detected")
    if r["out_of_range"] > 0:
        alerts.append("cels_out_of_range")
    alerts += [f"full_canvas_cels:{s['name']}" for s in stats if s["full_canvas_cels"] > 0]
    if alerts:
        result["alerts"] = alerts
    samples = r["overlap_samples"] or []
    if samples:
        result["overlap_samples"] = [_overlap_json(o) for o in samples]
    return json.dumps(result)
