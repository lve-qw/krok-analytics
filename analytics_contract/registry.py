"""Closed vocabularies for `tools` and `integrations`.

`config.py` already declares `FIXED_TOOLS` and `FIXED_INTEGRATIONS`, but until
now nothing used them: the LLM emitted free-form names. This module makes that
declaration the single source of truth for both normalization (in
`analytics_export`) and validation, so a name that is not in the registry is
reported rather than silently accepted.

Matching is case-insensitive and alias-aware. `config.py` stays the only place
where the vocabularies themselves are defined; the aliases below only map
observed spellings onto those canonical values.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Spellings the LLM is likely to emit, mapped onto canonical registry values.
#: Keys are compared after lowercasing and stripping. Extend this map rather
#: than widening the registry, so the vocabulary stays closed.
TOOL_ALIASES: dict[str, str] = {
    "email": "mail",
    "e-mail": "mail",
    "почта": "mail",
    "outlook": "mail",
    "exchange": "mail",
    "web": "web_search",
    "websearch": "web_search",
    "internet": "web_search",
    "поиск": "web_search",
    "search": "web_search",
    "календарь": "calendar",
    "контакты": "contacts",
    "срм": "crm",
    "жира": "jira",
    "конфлюенс": "confluence",
    "питон": "python",
    "эксель": "excel",
    "spreadsheet": "excel",
    "файлы": "filesystem",
    "files": "filesystem",
    "презентация": "presentation",
    "slides": "presentation",
    "ppt": "powerpoint",
    "doc": "word",
    "docx": "word",
    "перевод": "translator",
    "саммаризация": "summarizer",
    "summary": "summarizer",
    "speech": "speech_to_text",
    "stt": "speech_to_text",
    "tts": "text_to_speech",
    "голос": "speech_to_text",
}

#: Same idea for integrations.
INTEGRATION_ALIASES: dict[str, str] = {
    "почта": "Mail",
    "email": "Mail",
    "e-mail": "Mail",
    "outlook365": "Outlook",
    "ms exchange": "Exchange",
    "календарь": "Calendar",
    "срм": "CRM",
    "crm-система": "CRM",
    "жира": "Jira",
    "конфлюенс": "Confluence",
    "исуп": "ISUP",
    "isu": "ISUP",
    "эксель": "Excel",
    "xlsx": "Excel",
    "spreadsheet": "Excel",
    "docx": "Word",
    "ppt": "PowerPoint",
    "powerpoint presentation": "PowerPoint",
    "ms teams": "Teams",
    "телеграм": "Telegram",
    "шарепоинт": "SharePoint",
    "onedrive/sharepoint": "OneDrive",
    "проект": "Project",
    "контакты": "Contacts",
    "база данных": "SQL",
    "database": "SQL",
    "api": "REST API",
    "rest": "REST API",
    "браузер": "Browser",
    "интернет": "Internet",
    "web": "Internet",
    "файловая система": "Filesystem",
    "files": "Filesystem",
}


@dataclass(frozen=True)
class Vocabulary:
    """A closed vocabulary with case-insensitive, alias-aware lookup."""

    name: str
    values: tuple[str, ...]
    aliases: dict[str, str]

    def __post_init__(self) -> None:
        lowered = {value.lower(): value for value in self.values}
        object.__setattr__(self, "_lowered", lowered)

    def normalize(self, raw: str) -> str | None:
        """Return the canonical value, or None when the name is unknown."""

        key = (raw or "").strip().lower()
        if not key:
            return None
        direct = getattr(self, "_lowered").get(key)
        if direct is not None:
            return direct
        alias = self.aliases.get(key)
        if alias is not None:
            return alias
        # Registry values use both snake_case and spaced forms; try both.
        collapsed = key.replace(" ", "_")
        return getattr(self, "_lowered").get(collapsed)

    def __contains__(self, value: object) -> bool:
        return isinstance(value, str) and value in self.values


def load_project_registries() -> tuple[Vocabulary, Vocabulary] | None:
    """Load `FIXED_TOOLS` and `FIXED_INTEGRATIONS` from the project config.

    Returns None when `config.py` is not importable, so the validator stays
    usable outside this repository.
    """

    try:
        from config import config  # type: ignore[import-not-found]
    except Exception:
        return None

    tools = Vocabulary("tools", tuple(config.tools.FIXED_TOOLS), TOOL_ALIASES)
    integrations = Vocabulary(
        "integrations", tuple(config.integrations.FIXED_INTEGRATIONS), INTEGRATION_ALIASES
    )
    return tools, integrations
