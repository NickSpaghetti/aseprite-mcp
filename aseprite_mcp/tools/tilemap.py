import json
from typing import List, Dict, Any

from ..core.commands import call
from ..core.boundary import require_color, require_file, require_ints, require_point
from ..core.errors import InputError
from .. import mcp


@mcp.tool()
async def create_tilemap_layer(
    filename: str,
    layer_name: str,
    tile_width: int,
    tile_height: int,
) -> str:
    """Create a tilemap layer with its own tileset.

    Sets the sprite grid to the tile size and adds a tilemap layer.
    Tile index 0 is always the empty tile; add real tiles with
    draw_on_tile (which creates tiles on demand).

    Args:
        filename: Aseprite file to modify
        layer_name: Name for the new tilemap layer
        tile_width: Tile width in pixels
        tile_height: Tile height in pixels
    """
    require_file(filename)
    if tile_width <= 0 or tile_height <= 0:
        raise InputError("Tile dimensions must be > 0")

    await call("tilemap.create_layer", filename, name=layer_name, tile_width=tile_width, tile_height=tile_height)
    return (
        f"Tilemap layer '{layer_name}' created with {tile_width}x{tile_height} "
        f"tiles in {filename}"
    )


@mcp.tool()
async def draw_on_tile(
    filename: str,
    layer_name: str,
    tile_index: int,
    pixels: List[Dict[str, Any]],
) -> str:
    """Draw pixels onto a tile in a tilemap layer's tileset.

    Coordinates are tile-local (0,0 = tile top-left). When tile_index
    equals the current tile count, a new tile is appended automatically.

    Args:
        filename: Aseprite file to modify
        layer_name: Tilemap layer whose tileset to edit
        tile_index: Tile to draw on (1 = first real tile; 0 is reserved
            for the empty tile and cannot be drawn on)
        pixels: List of {"x": int, "y": int, "color": hex} where color is
            "#RGB", "#RRGGBB" or "#RRGGBBAA"
    """
    require_file(filename)
    if tile_index < 1:
        raise InputError("tile_index must be >= 1 (tile 0 is the reserved empty tile)")
    if not pixels:
        raise InputError("Pixels list cannot be empty")
    parsed = [[*require_point(p, "pixel"), require_color(p.get("color"))] for p in pixels]

    await call("tilemap.draw_on_tile", filename, layer=layer_name, index=tile_index, pixels=parsed)
    return (
        f"Drew {len(pixels)} pixels on tile {tile_index} of '{layer_name}' "
        f"in {filename}"
    )


@mcp.tool()
async def set_tiles(
    filename: str,
    layer_name: str,
    frame_index: int,
    tiles: List[Dict[str, Any]],
) -> str:
    """Place tiles on a tilemap layer by grid position.

    Args:
        filename: Aseprite file to modify
        layer_name: Tilemap layer to edit
        frame_index: Frame index starting at 1
        tiles: List of {"col": int, "row": int, "tile_index": int}
            (col/row are grid coordinates; tile_index 0 clears the cell)
    """
    require_file(filename)
    if not tiles:
        raise InputError("Tiles list cannot be empty")
    parsed = [require_ints(t, ("col", "row", "tile_index"), "tile") for t in tiles]

    await call("tilemap.set_tiles", filename, layer=layer_name, frame=frame_index, tiles=parsed)
    return (
        f"Placed {len(tiles)} tiles on '{layer_name}' frame {frame_index} "
        f"in {filename}"
    )


@mcp.tool()
async def get_tile_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    col: int,
    row: int,
) -> str:
    """Read which tile is placed at a grid position.

    Args:
        filename: Aseprite file to read
        layer_name: Tilemap layer to read
        frame_index: Frame index starting at 1
        col: Grid column (0-based)
        row: Grid row (0-based)

    Returns:
        JSON with {col, row, tile_index} (0 = empty).
    """
    require_file(filename)

    result = await call("tilemap.tile_at", filename, layer=layer_name, frame=frame_index, col=col, row=row)
    return json.dumps({"col": col, "row": row, "tile_index": result["tile_index"]})


@mcp.tool()
async def get_tilemap_info(filename: str, layer_name: str) -> str:
    """Get tilemap layer info: tile size, tile count, and map dimensions.

    Args:
        filename: Aseprite file to read
        layer_name: Tilemap layer to inspect

    Returns:
        JSON with tile_width, tile_height, tile_count (real tiles,
        excluding the empty tile 0), map_cols, map_rows.
    """
    require_file(filename)

    info = await call("tilemap.info", filename, layer=layer_name)
    keys = ("tile_width", "tile_height", "tile_count", "map_cols", "map_rows")
    return json.dumps({k: info[k] for k in keys})
