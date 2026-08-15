
import asyncio
from abc import ABC, abstractmethod
from starlette.websockets import WebSocketDisconnect


class OutputChannel(ABC):
    """Base interface — implemented by TerminalChannel and WebSocketChannel."""

    @abstractmethod
    async def send(self, message: str, msg_type: str = "agent") -> None:
        """Push a message to the user (no reply expected)."""

    @abstractmethod
    async def ask(self, question: str) -> str:
        """Push a question to the user and wait for their reply."""




class WebSocketChannel(OutputChannel):
    """
    Wraps a FastAPI WebSocket connection.
    Uses an asyncio.Queue to receive user answers asynchronously.
    """

    def __init__(self, websocket):
        self._ws = websocket
        self._reply_queue: asyncio.Queue = asyncio.Queue()
        self._disconnected: bool = False

    async def send(self, message: str, msg_type: str = "agent") -> None:
        """Send a message  """
        if self._disconnected:
            return
        try:
            await self._ws.send_json({
                "type":    msg_type,
                "content": message
            })
        except (WebSocketDisconnect, Exception):
            # Client closed the tab — mark as disconnected and continue pipeline
            self._disconnected = True
            print(f"[Channel] WebSocket disconnected. Continuing pipeline silently.")

    async def ask(self, question: str) -> str:
        """Ask a question — return empty string if client has disconnected."""
        await self.send(question, "ask_user")
        if self._disconnected:
            return ""
        answer = await self._reply_queue.get()
        return answer

    async def receive_reply(self, text: str) -> None:
        """Called by server.py whenever the browser sends a message during a task."""
        await self._reply_queue.put(text)
