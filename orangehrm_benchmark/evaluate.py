import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import time
import asyncio
import csv
from pathlib import Path

# Add src and root to sys path to import agent modules
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))
sys.path.insert(0, str(root_dir))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from tools.mcp_client import SERVER_PARAMS, navigate, get_snapshot
from orchestration.state import initiate_state
from orchestration.graph import build_graph
from utils.rag.retrieve import get_context

# Dummy Channel for Headless Execution (no WebSocket needed)
class DummyChannel:
    async def send(self, message: str, sender: str = "agent"):
        print(f"[{sender.upper()}] {message}")
    async def receive_reply(self, message: str):
        pass
    async def ask(self, question: str) -> str:
        print(f"\n[AGENT QUESTION] {question}")
        # Run input in executor to avoid blocking the asyncio event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, input, "Votre réponse > ")

async def run_benchmark():
    dataset_path = Path(__file__).parent / "dataset.json"
    results_path = Path(__file__).parent / "benchmark_results.csv"

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    tasks = dataset.get("tasks", [])

    print(f"=== Starting Benchmark: {dataset.get('benchmark_name')} ===")
    print(f"Loaded {len(tasks)} tasks.\n")

    results = []

    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            graph = build_graph(session)

            for task in tasks:
                print(f"\n--- Running Task: {task['id']} ({task['category']}) ---")
                print(f"Prompt: {task['prompt']}")

              
                print("[Evaluate] Démarrage du navigateur...")
                await navigate(session, "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login")
                
                input(f"\n[Evaluate] Veuillez préparer la page (login, navigation...) pour la tâche '{task['id']}', puis appuyez sur ENTRÉE pour lancer l'agent...")

                current_snapshot = await get_snapshot(session)

                
                current_url = "https://opensource-demo.orangehrmlive.com/"
                
               
                saas_context = get_context(task["prompt"], current_url=current_url)
                channel = DummyChannel()

                state = initiate_state(
                    user_task=task["prompt"],
                    saas_context=saas_context,
                    channel=channel
                )
                state["snapshot"] = current_snapshot 
                state["current_url"] = current_url
                state["conversation_history"] = []

                
                start_time = time.time()
                try:
                    final_state = await graph.ainvoke(state)
                except Exception as e:
                    print(f"[Evaluate] Agent Crashed: {e}")
                    final_state = state  
                    final_state["task_status"] = "crashed"
                end_time = time.time()

                execution_time = round(end_time - start_time, 2)
                step_count = final_state.get("step_count", 0)
                final_status = final_state.get("task_status", "unknown")
                final_message = final_state.get("final_message", "") or ""

                print(f"[Evaluate] Finished in {execution_time}s | Status: {final_status} | Steps: {step_count}")

                # 4. Resilience Metric — count errors that were followed by a successful recovery
                memory = final_state.get("memory", [])
                total_errors = sum(1 for m in memory if m.get("success") is False)
                errors_recovered = 0
                for i, m in enumerate(memory):
                    if m.get("success") is False:
                        # An error is "recovered" if any subsequent action succeeded
                        if any(m2.get("success") is True for m2 in memory[i + 1:]):
                            errors_recovered += 1

                results.append({
                    "Task ID": task["id"],
                    "Category": task["category"],
                    "Difficulty": task["difficulty"],
                    "Time (s)": execution_time,
                    "Steps": step_count,
                    "Agent Status": final_status,
                    "Errors Detected": total_errors,
                    "Errors Recovered": errors_recovered,
                    "Final Message": final_message,
                    "Human_Judge (0/1)": "", # To be filled manually
                    "Human_Comment": ""      # To be filled manually
                })

                print(f"[Evaluate] Metrics saved. Please evaluate task {task['id']} manually later.")

    # Save Results to CSV
    print("\n=== Benchmark Complete ===")
    if results:
        keys = results[0].keys()
        with open(results_path, "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, keys)
            dict_writer.writeheader()
            dict_writer.writerows(results)
        print(f"Results saved to: {results_path}")
        print("Please open the CSV file and fill in the 'Human_Judge (0/1)' and 'Human_Comment' columns.")

        # Print summary table (only system metrics)
        total = len(results)
        avg_time = round(sum(r["Time (s)"] for r in results) / total, 2)
        total_recovered = sum(r["Errors Recovered"] for r in results)
        print(f"\n--- System Summary ---")
        print(f"Tasks run    : {total}")
        print(f"Avg Time     : {avg_time}s per task")
        print(f"Errors Recovered : {total_recovered} self-corrections")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
