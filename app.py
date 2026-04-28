import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    config = uvicorn.Config("src.main:app", host="0.0.0.0", port=8000, reload=True)
    server = uvicorn.Server(config)
    asyncio.run(server.serve())