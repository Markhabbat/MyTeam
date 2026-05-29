import os
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv
from logger import get_logger

load_dotenv()

log = get_logger("agents")

llm = ChatAnthropic(
    model=os.getenv("MODEL_NAME", "claude-haiku-4-5-20251001"),
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=int(os.getenv("MAX_TOKENS", "4096"))
)

def architect_agent(task: str, context: str = "") -> str:
    log.info(f"[ARCHITECT] задача: {task[:80]}")
    log.debug(f"[ARCHITECT] контекст из памяти: {context[:200] if context else 'пусто'}")
    messages = [
        SystemMessage(content="""Ты Senior Software Architect.
Анализируй задачи и создавай чёткие технические планы.
Отвечай структурированно:
1. ПОНИМАНИЕ ЗАДАЧИ: что нужно сделать
2. ТЕХНИЧЕСКИЙ ПЛАН: пошаговый список
3. ТЕХНОЛОГИИ: какие использовать
4. РИСКИ: что может пойти не так"""),
        HumanMessage(content=f"Задача: {task}\nКонтекст: {context}")
    ]
    response = llm.invoke(messages)
    log.info(f"[ARCHITECT] план готов ({len(response.content)} символов)")
    log.debug(f"[ARCHITECT] ответ LLM:\n{response.content[:500]}")
    return response.content

def developer_agent(plan: str, task: str) -> str:
    log.info(f"[DEVELOPER] начинаю писать код для: {task[:80]}")
    messages = [
        SystemMessage(content="""Ты Senior Python Developer.
Пиши чистый, хорошо документированный код.
ВСЕГДА возвращай полный рабочий код с:
- docstrings для каждой функции
- обработкой ошибок через try/except
- примером использования в конце файла"""),
        HumanMessage(content=f"Задача: {task}\n\nПлан архитектора:\n{plan}\n\nНапиши код:")
    ]
    response = llm.invoke(messages)
    log.info(f"[DEVELOPER] код написан ({len(response.content)} символов)")
    log.debug(f"[DEVELOPER] ответ LLM:\n{response.content[:500]}")
    return response.content

def reviewer_agent(code: str, task: str) -> dict:
    log.info(f"[REVIEWER] проверяю код ({len(code)} символов)")
    messages = [
        SystemMessage(content="""Ты Senior Code Reviewer.
Проверяй код строго по этим критериям:
- Корректность логики
- Обработка ошибок
- Безопасность (SQL injection, secrets в коде)
- Читаемость и документация
- Производительность

Отвечай в формате:
ВЕРДИКТ: APPROVED или NEEDS_CHANGES
ОЦЕНКА: X/10
ПРОБЛЕМЫ: список проблем (или "нет")
УЛУЧШЕНИЯ: конкретные предложения"""),
        HumanMessage(content=f"Задача: {task}\n\nКод для ревью:\n{code}")
    ]
    response = llm.invoke(messages)
    review_text = response.content
    approved = "APPROVED" in review_text.upper()
    log.info(f"[REVIEWER] вердикт: {'APPROVED' if approved else 'NEEDS_CHANGES'}")
    log.debug(f"[REVIEWER] ревью:\n{review_text[:500]}")
    return {"review": review_text, "approved": approved}
