
import asyncio
from abc import ABC, abstractmethod


class OutputChannel(ABC):
    """Base interface — implemented by TerminalChannel and WebSocketChannel."""

    @abstractmethod
    async def send(self, message: str, msg_type: str = "agent") -> None:
        """Push a message to the user (no reply expected)."""

    @abstractmethod
    async def ask(self, question: str) -> str:
        """Push a question to the user and wait for their reply."""



class TerminalChannel(OutputChannel):

    async def send(self, message: str, msg_type: str = "agent") -> None:
        prefix = {
            "agent":    "[Agent]",
            "planner":  "[Planner]",
            "validator":"[Validator]",
            "success":  "[✅]",
            "error":    "[❌]",
        }.get(msg_type, "[Agent]")
        print(f"{prefix} {message}")

    async def ask(self, question: str) -> str:
        print(f"\n[Agent] ❓ {question}")
        return input("You : ").strip()


# ──────────────────────────────────────────────
# WebSocket implementation (used by server.py)
# ──────────────────────────────────────────────
class WebSocketChannel(OutputChannel):
    """
    Wraps a FastAPI WebSocket connection.
    Uses an asyncio.Queue to receive user answers asynchronously.
    """

    def __init__(self, websocket):
        self._ws = websocket
        self._reply_queue: asyncio.Queue = asyncio.Queue()

    async def send(self, message: str, msg_type: str = "agent") -> None:
        await self._ws.send_json({
            "type":    msg_type,
            "content": message
        })

    async def ask(self, question: str) -> str:
        # 1. Push the question to the browser
        await self._ws.send_json({
            "type":     "ask_user",
            "content":  question
        })
        
        answer = await self._reply_queue.get()
        return answer

    async def receive_reply(self, text: str) -> None:
        """Called by server.py whenever the browser sends a message during a task."""
        await self._reply_queue.put(text)
