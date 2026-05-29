from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from agents import architect_agent, developer_agent, reviewer_agent
from memory import get_memory_client, get_or_create_collection, save_memory, search_memory
from github_tools import push_to_github
from logger import get_logger
import docker
import tempfile
import os

log = get_logger("graph")

class DevTeamState(TypedDict):
    task: str
    plan: str
    code: str
    review: str
    approved: bool
    iterations: int
    final_output: str
    github_url: Optional[str]
    pr_url: Optional[str]

memory_client = get_memory_client()
code_collection = get_or_create_collection(memory_client, "code_solutions")

def run_code_in_docker(code: str) -> str:
    try:
        client = docker.from_env()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp_path = f.name
        result = client.containers.run(
            "python:3.11-slim",
            "python /code/script.py",
            volumes={tmp_path: {'bind': '/code/script.py', 'mode': 'ro'}},
            remove=True,
            timeout=30,
            mem_limit="128m",
            network_mode="none"
        )
        os.unlink(tmp_path)
        return result.decode('utf-8')[:2000]
    except Exception as e:
        return f"Ошибка выполнения: {e}"

def node_architect(state: DevTeamState) -> DevTeamState:
    log.info("=== УЗЕЛ: architect ===")
    similar = search_memory(code_collection, state["task"])
    context = "\n".join(similar) if similar else ""
    plan = architect_agent(state["task"], context)
    return {**state, "plan": plan}

def node_developer(state: DevTeamState) -> DevTeamState:
    log.info(f"=== УЗЕЛ: developer (итерация {state.get('iterations', 0) + 1}) ===")
    code = developer_agent(state["plan"], state["task"])
    return {**state, "code": code}

def node_reviewer(state: DevTeamState) -> DevTeamState:
    log.info("=== УЗЕЛ: reviewer ===")
    result = reviewer_agent(state["code"], state["task"])
    iterations = state.get("iterations", 0) + 1
    log.info(f"[REVIEWER] итерация {iterations}, approved={result['approved']}")
    return {
        **state,
        "review": result["review"],
        "approved": result["approved"],
        "iterations": iterations
    }

def node_finalize(state: DevTeamState) -> DevTeamState:
    log.info("=== УЗЕЛ: finalize ===")
    save_memory(code_collection, state["task"][:50], state["code"], {"task": state["task"]})
    output = f"✓ ЗАДАЧА ВЫПОЛНЕНА\n\nПЛАН:\n{state['plan']}\n\nКОД:\n{state['code']}\n\nРЕВЬЮ:\n{state['review']}"
    log.info(f"[FINALIZE] задача завершена, approved={state.get('approved')}")
    return {**state, "final_output": output, "github_url": "", "pr_url": ""}

def node_github(state: DevTeamState) -> DevTeamState:
    log.info("=== УЗЕЛ: github ===")
    try:
        result = push_to_github(
            state["task"], state["code"], state["plan"], state.get("review", "")
        )
        github_url = result["repo_url"]
        pr_url = result["pr_url"]
        files = ", ".join(result["files"])
        log.info(f"[GITHUB] репо: {github_url} | PR: {pr_url} | файлы: {files}")
        output = (
            state["final_output"]
            + f"\n\n🐙 GITHUB: {github_url}"
            + f"\n🔀 PULL REQUEST: {pr_url}"
            + f"\nФайлы: {files}"
        )
        return {**state, "github_url": github_url, "pr_url": pr_url, "final_output": output}
    except Exception as e:
        log.error(f"[GITHUB] ошибка: {e}", exc_info=True)
        output = state["final_output"] + f"\n\n⚠️ GitHub: не удалось запушить — {e}"
        return {**state, "github_url": "", "pr_url": "", "final_output": output}

def should_continue(state: DevTeamState) -> str:
    if state.get("approved"):
        return "approved"
    elif state.get("iterations", 0) >= 3:
        return "max_iterations"
    return "revise"

def build_graph():
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    db_path = os.getenv("SQLITE_DB_PATH", "./checkpoints.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    graph = StateGraph(DevTeamState)
    graph.add_node("architect", node_architect)
    graph.add_node("developer", node_developer)
    graph.add_node("reviewer", node_reviewer)
    graph.add_node("finalize", node_finalize)
    graph.add_node("github", node_github)
    graph.set_entry_point("architect")
    graph.add_edge("architect", "developer")
    graph.add_edge("developer", "reviewer")
    graph.add_conditional_edges("reviewer", should_continue, {
        "approved": "finalize",
        "revise": "developer",
        "max_iterations": "finalize"
    })
    graph.add_edge("finalize", "github")
    graph.add_edge("github", END)
    return graph.compile(checkpointer=checkpointer)
