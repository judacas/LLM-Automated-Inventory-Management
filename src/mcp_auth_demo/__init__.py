"""Isolated demo for trusted app-bound identity with MCP tool calls.

This package shows a minimal pattern where:
- the application chooses a trusted user identity,
- that identity is bound to the MCP client/session at the app layer,
- and the MCP server enforces authorization independently of anything the model says.
"""
