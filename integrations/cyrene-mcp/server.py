"""Cyrene tools for any MCP stdio client. Run with the backend virtualenv Python."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from mcp.server.fastmcp import FastMCP
from cyrene_control import request

mcp = FastMCP('Cyrene Desktop')

@mcp.tool()
def cyrene_state() -> dict:
    """Read connected clients, readiness, facial expressions, layout and task state."""
    return request('/state')

@mcp.tool()
def cyrene_command(name: str, data: dict, request_id: str | None = None) -> dict:
    """Send a Cyrene command. Read state.commands for capabilities. Accepted is not applied; events contain acknowledgements."""
    return request('/commands', {'name': name, 'data': data, 'request_id': request_id, 'source': 'mcp'})

@mcp.tool()
def cyrene_events(after: int = 0) -> dict:
    """Read events after a monotonic cursor, including command.applied/failed and speech lifecycle."""
    if after < 0: raise ValueError('after must be nonnegative')
    return request(f'/events?after={after}')

if __name__ == '__main__':
    mcp.run(transport='stdio')
