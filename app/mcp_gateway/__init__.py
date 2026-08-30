"""Authenticated MCP gateway for the hosted LEAGUEPILOT control plane."""

from app.mcp_gateway.server import create_mcp_server

__all__ = ["create_mcp_server"]
