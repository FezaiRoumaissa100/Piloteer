import os
import sys
import json
import uuid
import time
import asyncio
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir / "src"))
sys.path.insert(0, str(root_dir))

load_dotenv(root_dir / ".env")

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, navigate, get_snapshot
from orchestration.state import initiate_state
from orchestration.graph import build_graph
from utils.rag.retrieve import get_context
from langsmith import Client

LANGSMITH_PROJECT = os.getenv("LANGCHAIN_PROJECT", "evaluation")

class ConsoleAuditChannel:
    async def send(self, message: str, sender: str = "agent"):
        print(f"[{sender.upper()}] {message}")

    async def receive_reply(self, message: str):
        pass

    async def ask(self, question: str) -> str:
        print(f"\n[HITL REQUIRED]\nQuestion: {question}")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, input, "Your Reply > ")

async def _fetch_langsmith_metrics(client: Client, run_id: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            run = client.read_run(run_id=str(run_id))
            input_tokens  = run.prompt_tokens or 0
            output_tokens = run.completion_tokens or 0
            total_tokens  = run.total_tokens or (input_tokens + output_tokens)
            latency_s = 0.0
            if run.end_time and run.start_time:
                latency_s = round((run.end_time - run.start_time).total_seconds(), 2)
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "latency_s": latency_s
            }
        except Exception:
            if attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "latency_s": 0.0}

def get_last_task_id(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            if not reader:
                return 0
            last_id_str = reader[-1].get("Task ID", "M-000")
            return int(last_id_str.split("-")[1])
    except Exception:
        return 0

async def main():
    client = Client()
    results_path = root_dir / "results.csv"
    task_counter = get_last_task_id(results_path) + 1

    print("-----Evaluation----")

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            graph = build_graph(session)

            while True:
                prompt = input(f"\nTask #{task_counter} (or 'exit') > ").strip()
                if not prompt or prompt.lower() == "exit":
                    break

                task_type = input("Task Type > ").strip() or "General"
                mode = input("Execution Mode (Question/Guide/Execute) [Execute] > ").strip() or "Execute"

                print("Navigating to OrangeHRM...")
                await navigate(session, "https://opensource-demo.orangehrmlive.com/web/index.php/dashboard/index")
                input("Ready? Press ENTER to start.")

                current_snapshot = await get_snapshot(session)
                current_url = "https://opensource-demo.orangehrmlive.com/"
                saas_context = "use your knowledge of the OrangeHRM application to complete the task."
                channel = ConsoleAuditChannel()

                state = initiate_state(user_task=prompt, saas_context=saas_context, channel=channel)
                state.update({
                    "snapshot": current_snapshot,
                    "current_url": current_url,
                    "conversation_history": [],
                    "execution_mode": mode.upper()
                })

                run_id = uuid.uuid4()
                print(f"Running agent (Run ID: {run_id})...")
                
                start_wall = time.time()
                try:
                    final_state = await graph.ainvoke(
                        state,
                        config={
                            "run_id": run_id,
                            "run_name": f"task_{task_counter}",
                            "tags": ["type", task_type.lower()],
                            "metadata": {"user_task": prompt, "mode": mode}
                        }
                    )
                except Exception as e:
                    print(f"Error: {e}")
                    final_state = state
                    final_state["task_status"] = "crashed"
                end_wall = time.time()

                wall_time = round(end_wall - start_wall, 2)
                metrics = await _fetch_langsmith_metrics(client, run_id)
                memory = final_state.get("memory", [])
                
                recovery_triggered = 1 if any(m.get("success") is False for m in memory) else 0
                guardrail_triggered = 1 if any("guardrail" in str(m).lower() for m in memory) else 0

                print(f"\nMetrics: {metrics['latency_s'] or wall_time}s | {metrics['total_tokens']} tokens | {final_state.get('step_count', 0)} steps")
                
                success_val = 1 if input("Success? (y/n) > ").strip().lower() in ["y", "yes", "1"] else 0
                recovery_success = ""
                if recovery_triggered:
                    recovery_success = 1 if input("Recovery successful? (y/n) > ").strip().lower() in ["y", "yes", "1"] else 0
                comments = input("Comments > ").strip()

                row = {
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Task ID": f"M-{task_counter:03d}",
                    "Task Prompt": prompt,
                    "Task Type": task_type,
                    "Mode": mode,
                    "Success (0/1)": success_val,
                    "Recovery Triggered (0/1)": recovery_triggered,
                    "Recovery Success (0/1)": recovery_success,
                    "Guardrail Triggered (0/1)": guardrail_triggered,
                    "Duration (s)": metrics["latency_s"] or wall_time,
                    "Input Tokens": metrics["input_tokens"],
                    "Output Tokens": metrics["output_tokens"],
                    "Total Tokens": metrics["total_tokens"],
                    "Steps": final_state.get("step_count", 0),
                    "Agent Status": final_state.get("task_status", "unknown"),
                    "Narration Quality (1-5)": "",
                    "Educational Value (1-5)": "",
                    "Comments": comments
                }

                file_exists = results_path.exists()
                with open(results_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=row.keys())
                    if not file_exists:
                        writer.writeheader()
                    writer.writerow(row)
                
                print(f"Result saved to {results_path.name}")
                task_counter += 1

if __name__ == "__main__":
    asyncio.run(main())
