"""The two ways a tool call fails.

Both subclass FastMCP's ToolError, so a raised error reaches the MCP client as
a result with isError=True instead of a successful result holding error text.
"""

from mcp.server.fastmcp.exceptions import ToolError


class InputError(ToolError):
    """A tool argument was rejected before Aseprite ran."""


class AsepriteError(ToolError):
    """Aseprite failed, or an op or script reported failure.

    `code` is the op's failure code (for example "LayerNotFound") when there is one.
    """

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code
