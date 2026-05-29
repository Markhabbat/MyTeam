from graph import build_graph
from history import save_run
from logger import get_logger
from rich.panel import Panel
from rich.console import Console
import uuid

console = Console()
log = get_logger("main")

def run_dev_team(task: str) -> dict:
    log.info(f"{'='*60}")
    log.info(f"НОВАЯ ЗАДАЧА: {task}")
    log.info(f"{'='*60}")
    console.print(Panel(f"[bold cyan]Задача:[/] {task}", title="🚀 ИИ Команда"))
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    initial_state = {
        "task": task, "plan": "", "code": "",
        "review": "", "approved": False,
        "iterations": 0, "final_output": "",
        "github_url": "", "pr_url": ""
    }
    console.print("[yellow]🏗  Архитектор создаёт план...[/]")
    result = graph.invoke(initial_state, config=config)
    save_run(task, result)
    log.info(f"ЗАДАЧА ЗАВЕРШЕНА | approved={result.get('approved')} | iterations={result.get('iterations')} | github={result.get('github_url', '-')}")
    console.print(Panel(result["final_output"], title="✅ Результат"))
    if result.get("github_url"):
        console.print(f"\n[bold green]🐙 GitHub:[/] {result['github_url']}")
    if result.get("pr_url"):
        console.print(f"[bold magenta]🔀 Pull Request:[/] {result['pr_url']}")
    return result

if __name__ == "__main__":
    run_dev_team("Напиши Python функцию для парсинга CSV файла и подсчёта статистики по колонкам")
