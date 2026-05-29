from github import Github, Auth, GithubException
import os
import re
from dotenv import load_dotenv

load_dotenv()

def get_github_client():
    token = os.getenv("GITHUB_TEAM_TOKEN")
    if not token:
        raise ValueError("GITHUB_TEAM_TOKEN не задан в .env")
    return Github(auth=Auth.Token(token))

def get_target_repo():
    """Возвращает репозиторий Experiment — единое место работы агентов."""
    repo_full_name = os.getenv("GITHUB_TARGET_REPO", "Markhabbat/Experiment")
    g = get_github_client()
    return g.get_repo(repo_full_name)

def task_to_branch_name(task: str) -> str:
    """Превращает текст задачи в имя ветки вида ai/название-задачи."""
    name = task.lower()[:40]
    name = re.sub(r'[^a-zа-яё0-9\s]', '', name)
    name = re.sub(r'\s+', '-', name.strip())
    translit = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
        'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
        'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
        'ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
    }
    result = ''.join(translit.get(c, c) for c in name)
    result = re.sub(r'-+', '-', result).strip('-')
    return f"ai/{result[:40]}" or "ai/task"

def extract_code_files(code_text: str) -> dict:
    """Извлекает именованные файлы из текста агента."""
    files = {}
    pattern = re.findall(
        r'(?:файл\s*\d*\s*:?\s*`?([a-zA-Z0-9_\-\.]+\.[a-zA-Z]+)`?|##\s*\*?\*?`?([a-zA-Z0-9_\-\.]+\.[a-zA-Z]+)`?\*?\*?)'
        r'.*?```(?:python|txt|markdown|bash|env)?\n(.*?)```',
        code_text, re.DOTALL | re.IGNORECASE
    )
    for m in pattern:
        fname = (m[0] or m[1]).strip()
        content = m[2].strip()
        if fname and content:
            files[fname] = content
    if not files:
        blocks = re.findall(r'```(?:python)?\n(.*?)```', code_text, re.DOTALL)
        if blocks:
            files["main.py"] = blocks[0].strip()
    return files

def create_branch(repo, branch_name: str, from_branch: str = "test") -> str:
    """Создаёт ветку от from_branch. Если уже есть — возвращает как есть."""
    try:
        base_sha = repo.get_branch(from_branch).commit.sha
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
        print(f"  Ветка создана: {branch_name} (от {from_branch})")
    except GithubException as e:
        if e.status == 422:
            print(f"  Ветка уже существует: {branch_name}")
        else:
            raise
    return branch_name

def commit_files_to_branch(repo, files: dict, branch: str, commit_message: str) -> list:
    """Коммитит файлы в указанную ветку."""
    committed = []
    for filename, content in files.items():
        try:
            try:
                existing = repo.get_contents(filename, ref=branch)
                repo.update_file(filename, commit_message, content, existing.sha, branch=branch)
            except GithubException:
                repo.create_file(filename, commit_message, content, branch=branch)
            print(f"  ✓ {filename}")
            committed.append(filename)
        except Exception as e:
            print(f"  ✗ {filename}: {e}")
    return committed

def create_pull_request(repo, branch: str, task: str, plan: str, review: str) -> str:
    """Открывает PR из ветки агента в test, назначает владельца ревьюером."""
    base_branch = os.getenv("GITHUB_BASE_BRANCH", "test")
    reviewer = os.getenv("GITHUB_USERNAME", "")
    title = f"feat: {task[:72]}"
    body = (
        f"## Задача\n{task}\n\n"
        f"## План архитектора\n{plan[:800]}\n\n"
        f"## Ревью агента\n{review[:800]}\n\n"
        f"---\n"
        f"> ⚠️ PR создан ИИ-агентом. Требует проверки и одобрения перед мёрджем в `{base_branch}`.\n\n"
        f"*Сгенерировано командой ИИ-агентов*"
    )
    pr = repo.create_pull(
        title=title,
        body=body,
        head=branch,
        base=base_branch
    )
    if reviewer:
        try:
            pr.create_review_request(reviewers=[reviewer])
            print(f"  Ревьюер назначен: @{reviewer}")
        except GithubException as e:
            print(f"  Ревьюер не назначен (owner limitation): {e.data.get('message', e)}")
    print(f"  PR открыт: {pr.html_url}")
    return pr.html_url

def push_to_github(task: str, code_text: str, plan: str, review: str = "") -> dict:
    """
    Главная функция: коммитит код в ветку задачи в Experiment
    и открывает PR в ветку test.
    """
    repo = get_target_repo()
    branch_name = task_to_branch_name(task)

    files = extract_code_files(code_text)
    readme = (
        f"## {task[:80]}\n\n"
        f"### План\n\n{plan[:600]}\n\n"
        f"*Сгенерировано командой ИИ-агентов*\n"
    )
    # Кладём файлы в папку с именем ветки чтобы не конфликтовали задачи
    folder = branch_name.replace("ai/", "")
    prefixed_files = {f"{folder}/{name}": content for name, content in files.items()}
    prefixed_files[f"{folder}/README.md"] = readme

    print(f"\n  GitHub [{repo.full_name}]: создаю ветку '{branch_name}'...")
    create_branch(repo, branch_name, from_branch="master")

    print(f"  GitHub: коммичу {len(prefixed_files)} файл(ов)...")
    commit_files_to_branch(repo, prefixed_files, branch_name, f"feat: {task[:72]}")

    print(f"  GitHub: открываю Pull Request → test...")
    pr_url = create_pull_request(repo, branch_name, task, plan, review)

    return {
        "repo_url": repo.html_url,
        "pr_url": pr_url,
        "files": list(prefixed_files.keys())
    }

# ── вспомогательные функции ──────────────────────────────────────────────────

def get_repo_contents(path: str = "") -> str:
    repo = get_target_repo()
    contents = repo.get_contents(path)
    return "\n".join(f"{c.type}: {c.path}" for c in contents)

def create_issue(title: str, body: str) -> str:
    repo = get_target_repo()
    issue = repo.create_issue(title=title, body=body)
    return f"Issue создан: {issue.html_url}"
