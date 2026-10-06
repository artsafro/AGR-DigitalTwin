"""Run upstream multiCAD tools on one COM thread without its web dashboard."""
import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

import pythoncom
from fastmcp import FastMCP


def initialize_com():
    pythoncom.CoInitialize()


worker = ThreadPoolExecutor(max_workers=1, initializer=initialize_com,
                            thread_name_prefix="multicad-com")
original_tool = FastMCP.tool


def serialized_tool(self, *args, **kwargs):
    register = original_tool(self, *args, **kwargs)

    def decorate(function):
        @wraps(function)
        async def on_com_thread(*call_args, **call_kwargs):
            future = worker.submit(function, *call_args, **call_kwargs)
            return await asyncio.wrap_future(future)

        if function.__name__ == "manage_files":
            on_com_thread.__doc__ = (function.__doc__ or "") + '''
            Project additions (JSON operations):
            [{"action":"info"}] returns active path, saved state, INSUNITS/count.
            [{"action":"open","filepath":"C:/existing.dwg"}] opens DWG/DXF.
            Save requires a new versioned path under this project or configured
            export directory; only DWG/DXF supported, never overwrite. Response
            reports actual saved path, format, size and SHA256. PDF unsupported.
            '''
        if function.__name__ == "draw_entities":
            on_com_thread.__doc__ = (function.__doc__ or "") + '''
            Project spline route supports open cubic fit-point splines only;
            closed or noncubic requests are rejected before entity creation.
            '''
        return register(on_com_thread)

    return decorate


if __name__ == "__main__":
    # Upstream synchronous tools otherwise run in different pool threads;
    # its adapter proxies are thread-local, so status can lose the connection.
    FastMCP.tool = serialized_tool
    try:
        # Register the installed upstream tools directly. Importing server.py
        # also opens an installation-folder log and initializes a web dashboard.
        from mcp_tools.tools import (
            register_session_tools, register_drawing_tools, register_layer_tools,
            register_file_tools, register_entity_tools, register_export_tools,
            register_block_tools,
        )
        from multicad_compat import install
        install()
        logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
        mcp = FastMCP(name="multiCAD-MCP")
        for register in (
            register_session_tools, register_drawing_tools, register_layer_tools,
            register_file_tools, register_entity_tools, register_export_tools,
            register_block_tools,
        ):
            register(mcp)
    finally:
        FastMCP.tool = original_tool
    try:
        mcp.run(transport="stdio")
    finally:
        worker.shutdown(wait=True)
