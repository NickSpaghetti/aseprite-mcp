from typing import List, Dict, Any

from ..core.commands import call
from ..core.boundary import require_color, require_file, require_point
from ..core.errors import InputError
from .. import mcp


def _pixels(pixels: List[Dict[str, Any]]) -> list[list]:
    """[{"x", "y", "color"}] -> [[x, y, [r, g, b, a]]]; color defaults to black."""
    return [[*require_point(p, "pixel"), require_color(p.get("color", "#000000"))] for p in pixels]


def _points(points: List[Dict[str, int]]) -> list[list[int]]:
    return [require_point(p) for p in points]


def _at(layer_name: str, frame_index: int, create_if_missing: bool) -> dict:
    """Target arguments shared by the *_at tools."""
    return {"layer": layer_name, "frame": frame_index, "create": create_if_missing}


@mcp.tool()
async def draw_pixels(filename: str, pixels: List[Dict[str, Any]]) -> str:
    """Draw pixels on the canvas with specified colors.

    Draws on the sprite's only layer, frame 1; on a sprite with several
    layers it fails, so use the _at version and name the layer.

    Args:
        filename: Name of the Aseprite file to modify
        pixels: List of pixel data, each containing:
            {"x": int, "y": int, "color": str}
            where color is a hex code like "#FF0000"
    """
    require_file(filename)

    await call("drawing.pixels", filename, pixels=_pixels(pixels))
    return f"Pixels drawn successfully in {filename}"


@mcp.tool()
async def draw_line(filename: str, x1: int, y1: int, x2: int, y2: int, color: str = "#000000", thickness: int = 1) -> str:
    """Draw a line on the canvas.

    Draws on the sprite's only layer, frame 1; on a sprite with several
    layers it fails, so use the _at version and name the layer.

    Args:
        filename: Name of the Aseprite file to modify
        x1: Starting x coordinate
        y1: Starting y coordinate
        x2: Ending x coordinate
        y2: Ending y coordinate
        color: Hex color code (default: "#000000")
        thickness: Line thickness in pixels (default: 1)
    """
    require_file(filename)

    await call("drawing.path", filename, points=[[x1, y1], [x2, y2]], color=require_color(color),
               thickness=thickness)
    return f"Line drawn successfully in {filename}"


@mcp.tool()
async def draw_rectangle(filename: str, x: int, y: int, width: int, height: int, color: str = "#000000", fill: bool = False) -> str:
    """Draw a rectangle on the canvas.

    Draws on the sprite's only layer, frame 1; on a sprite with several
    layers it fails, so use the _at version and name the layer.

    Args:
        filename: Name of the Aseprite file to modify
        x: Top-left x coordinate
        y: Top-left y coordinate
        width: Width of the rectangle in pixels (must be > 0)
        height: Height of the rectangle in pixels (must be > 0)
        color: Hex color code (default: "#000000")
        fill: Whether to fill the rectangle (default: False)
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    await call("drawing.rectangle", filename, x=x, y=y, width=width, height=height,
               color=require_color(color), fill=fill)
    return f"Rectangle drawn successfully in {filename}"


@mcp.tool()
async def fill_area(filename: str, x: int, y: int, color: str = "#000000") -> str:
    """Fill an area with color using the paint bucket tool.

    Draws on the sprite's only layer, frame 1; on a sprite with several
    layers it fails, so use the _at version and name the layer.

    Args:
        filename: Name of the Aseprite file to modify
        x: X coordinate to fill from
        y: Y coordinate to fill from
        color: Hex color code (default: "#000000")
    """
    require_file(filename)

    await call("drawing.fill", filename, x=x, y=y, color=require_color(color))
    return f"Area filled successfully in {filename}"


@mcp.tool()
async def draw_circle(filename: str, center_x: int, center_y: int, radius: int, color: str = "#000000", fill: bool = False) -> str:
    """Draw a circle on the canvas.

    Draws on the sprite's only layer, frame 1; on a sprite with several
    layers it fails, so use the _at version and name the layer.

    Args:
        filename: Name of the Aseprite file to modify
        center_x: X coordinate of circle center
        center_y: Y coordinate of circle center
        radius: Radius of the circle in pixels
        color: Hex color code (default: "#000000")
        fill: Whether to fill the circle (default: False)
    """
    require_file(filename)

    await call("drawing.ellipse", filename, cx=center_x, cy=center_y, rx=radius, ry=radius,
               color=require_color(color), fill=fill)
    return f"Circle drawn successfully in {filename}"


@mcp.tool()
async def draw_pixels_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    pixels: List[Dict[str, Any]],
    create_if_missing: bool = True
) -> str:
    """Draw pixels on a specific layer/frame.

    Args:
        filename: Name of the Aseprite file to modify
        layer_name: Layer name to target
        frame_index: Frame index starting at 1
        pixels: List of pixel data with x/y/color
        create_if_missing: Create cel if it does not exist
    """
    require_file(filename)

    await call("drawing.pixels", filename, pixels=_pixels(pixels),
               **_at(layer_name, frame_index, create_if_missing))
    return f"Pixels drawn on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def draw_line_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: str = "#000000",
    thickness: int = 1,
    create_if_missing: bool = True
) -> str:
    """Draw a line on a specific layer/frame.

    Args:
        filename (str): The path to the Aseprite file.
        layer_name (str): The name of the layer to draw on.
        frame_index (int): The index of the frame to draw on.
        x1 (int): The x coordinate of the first point of the line.
        y1 (int): The y coordinate of the first point of the line.
        x2 (int): The x coordinate of the second point of the line.
        y2 (int): The y coordinate of the second point of the line.
        color (str, optional): The color to draw the line with. Defaults to "#000000".
        thickness (int, optional): The thickness of the line. Defaults to 1.
        create_if_missing (bool, optional): Whether to create the layer if it doesn't exist. Defaults to True.
    """
    require_file(filename)

    await call("drawing.path", filename, points=[[x1, y1], [x2, y2]], color=require_color(color),
               thickness=thickness, **_at(layer_name, frame_index, create_if_missing))
    return f"Line drawn on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def draw_rectangle_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    color: str = "#000000",
    fill: bool = False,
    create_if_missing: bool = True
) -> str:
    """Draw a rectangle on a specific layer/frame.

    Args:
        filename (str): The path to the Aseprite file.
        layer_name (str): The name of the layer to draw on.
        frame_index (int): The index of the frame to draw on.
        x (int): The x coordinate of the top-left corner of the rectangle.
        y (int): The y coordinate of the top-left corner of the rectangle.
        width (int): The width of the rectangle.
        height (int): The height of the rectangle.
        color (str, optional): The color to draw the rectangle with. Defaults to "#000000".
        fill (bool, optional): Whether to fill the rectangle. Defaults to False.
        create_if_missing (bool, optional): Whether to create the layer if it doesn't exist. Defaults to True.
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    await call("drawing.rectangle", filename, x=x, y=y, width=width, height=height,
               color=require_color(color), fill=fill, **_at(layer_name, frame_index, create_if_missing))
    return f"Rectangle drawn on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def draw_circle_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    center_x: int,
    center_y: int,
    radius: int,
    color: str = "#000000",
    fill: bool = False,
    create_if_missing: bool = True
) -> str:
    """Draw a circle on a specific layer/frame.

    Args:
        filename (str): The path to the Aseprite file.
        layer_name (str): The name of the layer to draw on.
        frame_index (int): The index of the frame to draw on.
        center_x (int): The x coordinate of the center of the circle.
        center_y (int): The y coordinate of the center of the circle.
        radius (int): The radius of the circle.
        color (str, optional): The color to draw the circle with. Defaults to "#000000".
        fill (bool, optional): Whether to fill the circle. Defaults to False.
        create_if_missing (bool, optional): Whether to create the layer if it doesn't exist. Defaults to True.
    """
    require_file(filename)

    await call("drawing.ellipse", filename, cx=center_x, cy=center_y, rx=radius, ry=radius,
               color=require_color(color), fill=fill, **_at(layer_name, frame_index, create_if_missing))
    return f"Circle drawn on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def fill_area_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    color: str = "#000000",
    create_if_missing: bool = True
) -> str:
    """Fill an area on a specific layer/frame.

    Args:
        filename (str): The path to the Aseprite file.
        layer_name (str): The name of the layer to draw on.
        frame_index (int): The index of the frame to draw on.
        x (int): The x coordinate of the point to start filling from.
        y (int): The y coordinate of the point to start filling from.
        color (str, optional): The color to fill the area with. Defaults to "#000000".
        create_if_missing (bool, optional): Whether to create the layer if it doesn't exist. Defaults to True.
    """
    require_file(filename)

    await call("drawing.fill", filename, x=x, y=y, color=require_color(color),
               **_at(layer_name, frame_index, create_if_missing))
    return f"Area filled on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def draw_polygon(
    filename: str,
    layer_name: str,
    frame_index: int,
    points: List[Dict[str, int]],
    color: str = "#000000",
    fill: bool = False,
    create_if_missing: bool = True
) -> str:
    """Draw a polygon on a specific layer/frame.

    Args:
        filename (str): The path to the Aseprite file.
        layer_name (str): The name of the layer to draw on.
        frame_index (int): The index of the frame to draw on.
        points (List[Dict[str, int]]): The list of points to draw the polygon.
        color (str, optional): The color to draw the polygon with. Defaults to "#000000".
        fill (bool, optional): Whether to fill the polygon. Defaults to False.
        create_if_missing (bool, optional): Whether to create the layer if it doesn't exist. Defaults to True.
    """
    require_file(filename)
    if len(points) < 3:
        raise InputError("Polygon requires at least 3 points")

    await call("drawing.polygon", filename, points=_points(points), color=require_color(color), fill=fill,
               **_at(layer_name, frame_index, create_if_missing))
    return f"Polygon drawn on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def draw_path(
    filename: str,
    layer_name: str,
    frame_index: int,
    points: List[Dict[str, int]],
    color: str = "#000000",
    thickness: int = 1,
    create_if_missing: bool = True
) -> str:
    """Draw a path using a polyline on a specific layer/frame.

    Args:
        filename (str): The path to the Aseprite file.
        layer_name (str): The name of the layer to draw on.
        frame_index (int): The index of the frame to draw on.
        points (List[Dict[str, int]]): The points to draw the path with.
        color (str, optional): The color to draw the path with. Defaults to "#000000".
        thickness (int, optional): The thickness of the path. Defaults to 1.
        create_if_missing (bool, optional): Whether to create the layer if it doesn't exist. Defaults to True.
    """
    require_file(filename)
    if len(points) < 2:
        raise InputError("Path requires at least 2 points")

    await call("drawing.path", filename, points=_points(points), color=require_color(color),
               thickness=thickness, **_at(layer_name, frame_index, create_if_missing))
    return f"Path drawn on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def apply_gradient_rect(
    filename: str,
    layer_name: str,
    frame_index: int,
    x: int,
    y: int,
    width: int,
    height: int,
    color_start: str,
    color_end: str,
    horizontal: bool = True,
    create_if_missing: bool = True
) -> str:
    """Apply a linear gradient fill to a rectangle.

    Args:
        filename (str): The path to the Aseprite file.
        layer_name (str): The name of the layer to draw on.
        frame_index (int): The index of the frame to draw on.
        x (int): The x coordinate of the rectangle to draw on.
        y (int): The y coordinate of the rectangle to draw on.
        width (int): The width of the rectangle to draw on.
        height (int): The height of the rectangle to draw on.
        color_start (str): The start color of the gradient.
        color_end (str): The end color of the gradient.
        horizontal (bool, optional): Whether to draw the gradient horizontally. Defaults to True.
        create_if_missing (bool, optional): Whether to create the layer if it doesn't exist. Defaults to True.
    """
    require_file(filename)
    if width <= 0 or height <= 0:
        raise InputError("Width and height must be > 0")

    await call("drawing.gradient", filename, x=x, y=y, width=width, height=height,
               color_start=require_color(color_start, "color_start"),
               color_end=require_color(color_end, "color_end"), horizontal=horizontal,
               **_at(layer_name, frame_index, create_if_missing))
    return f"Gradient applied on '{layer_name}' frame {frame_index} in {filename}"


@mcp.tool()
async def draw_ellipse_at(
    filename: str,
    layer_name: str,
    frame_index: int,
    center_x: int,
    center_y: int,
    radius_x: int,
    radius_y: int,
    color: str = "#000000",
    fill: bool = False,
    create_if_missing: bool = True
) -> str:
    """Draw an ellipse on a specific layer/frame.

    Args:
        filename: Aseprite file to modify
        layer_name: Layer to draw on
        frame_index: Frame index starting at 1
        center_x: Ellipse center x
        center_y: Ellipse center y
        radius_x: Horizontal radius in pixels
        radius_y: Vertical radius in pixels
        color: Hex color code (default "#000000")
        fill: Fill the ellipse instead of outlining it
        create_if_missing: Create the cel if it does not exist
    """
    require_file(filename)
    if radius_x <= 0 or radius_y <= 0:
        raise InputError("radius_x and radius_y must be > 0")

    await call("drawing.ellipse", filename, cx=center_x, cy=center_y, rx=radius_x, ry=radius_y,
               color=require_color(color), fill=fill, **_at(layer_name, frame_index, create_if_missing))
    return f"Ellipse drawn on '{layer_name}' frame {frame_index} in {filename}"
