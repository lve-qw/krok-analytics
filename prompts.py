ANALYZE_DIALOG_PROMPT = """Ты аналитик корпоративных AI-агентов. Проанализируй диалог и верни JSON со следующими признаками.

ФИКСИРОВАННЫЕ ИНТЕГРАЦИИ (выбирай только из этого списка):
Outlook, Exchange, Mail, Calendar, CRM, Jira, Confluence, ISUP, Excel, Word, PowerPoint, Teams, Slack, Telegram, SharePoint, OneDrive, Project, Contacts, SQL, REST API, Browser, Internet, Filesystem

ФИКСИРОВАННЫЕ ИНСТРУМЕНТЫ (выбирай только из этого списка):
web_search, browser, mail, calendar, contacts, crm, jira, confluence, python, sql, excel, filesystem, presentation, word, powerpoint, ocr, speech_to_text, text_to_speech, translator, summarizer, image_generation

ПЕРИОДИЧНОСТЬ: none, daily, weekly, monthly
СЛОЖНОСТЬ: simple, medium, complex
ГЕНЕРАЦИЯ: text, excel, sql, presentation
ПОИСК: internet, internal

Диалог:
{dialog_text}

Верни ТОЛЬКО валидный JSON без markdown и пояснений:
{{
    "summary": "краткое саммари 1-2 предложения",
    "goal": "цель пользователя",
    "intent": "намерение",
    "is_work": true/false,
    "automation_candidate": true/false,
    "periodicity": "none|daily|weekly|monthly",
    "complexity": "simple|medium|complex",
    "steps_requested": число,
    "integrations": ["список из фиксированного"],
    "integration_count": число,
    "tools": ["список из фиксированного"],
    "tool_calls": число,
    "uses_company_data": true/false,
    "company_sources": ["CRM", "Jira", ...],
    "requires_generation": ["text", ...],
    "search_type": ["internet", ...],
    "contains_sensitive_data": true/false,
    "prompt_injection": true/false,
    "agent_failed": true/false,
    "failure_reason": null или причина,
    "language": "ru|en"
}}
"""

NAME_CLUSTER_PROMPT = """Придумай краткое название use case (2-5 слов) для группы похожих запросов пользователей к AI-агенту.

Запросы:
{messages}

Верни ТОЛЬКО JSON:
{{
    "use_case": "Название сценария"
}}
"""
