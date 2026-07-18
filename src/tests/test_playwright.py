import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client 
from mcp_client import navigate, click, type_text, wait_for

SERVER_PARAMS = StdioServerParameters(
    command="npx",
    args=["@playwright/mcp@latest", "--caps=devtools"]
)

async def main():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await navigate(session, "https://www.google.com")
            await session.call_tool("browser_video_show_actions", arguments={
                "cursor": "pointer",
                "duration": 800,
                "position": "top-right"
            })
            await click(session, "e43")
            await type_text(session, "e43", "Piloteer agent IA")
            await click(session, "e70")
            await wait_for(session, 3)

asyncio.run(main())