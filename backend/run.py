"""Dev/prod runner.

On Windows the Agent SDK needs the Proactor event loop (its transport is a CLI
subprocess), but uvicorn's --reload mode installs the Selector loop, which cannot
spawn subprocesses. So: run without reload and pin the Proactor policy explicitly.
"""

import asyncio
import sys

import uvicorn

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
