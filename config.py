from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class ModelConfig:
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    zero_shot_model: str = "facebook/bart-large-mnli"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    device: str = "auto"
    max_tokens: int = 2048
    temperature: float = 0.1


@dataclass
class ClassificationConfig:
    confidence_threshold: float = 0.5
    default_class: str = "other"


@dataclass
class ClusteringConfig:
    min_cluster_size: int = 5
    min_samples: int = 3
    top_n_for_naming: int = 30


@dataclass
class PathsConfig:
    base_dir: Path = Path(__file__).parent
    data_dir: Path = base_dir / "data"
    dialogs_dir: Path = data_dir / "dialogs"
    outputs_dir: Path = base_dir / "outputs"
    models_dir: Path = base_dir / "models"
    classes_file: Path = data_dir / "classes.csv"


@dataclass
class IntegrationsConfig:
    FIXED_INTEGRATIONS: tuple = (
        "Outlook", "Exchange", "Mail", "Calendar", "CRM", "Jira", "Confluence",
        "ISUP", "Excel", "Word", "PowerPoint", "Teams", "Slack", "Telegram",
        "SharePoint", "OneDrive", "Project", "Contacts", "SQL", "REST API",
        "Browser", "Internet", "Filesystem"
    )


@dataclass
class ToolsConfig:
    FIXED_TOOLS: tuple = (
        "web_search", "browser", "mail", "calendar", "contacts", "crm", "jira",
        "confluence", "python", "sql", "excel", "filesystem", "presentation",
        "word", "powerpoint", "ocr", "speech_to_text", "text_to_speech",
        "translator", "summarizer", "image_generation"
    )


@dataclass
class Config:
    models: ModelConfig = ModelConfig()
    classification: ClassificationConfig = ClassificationConfig()
    clustering: ClusteringConfig = ClusteringConfig()
    paths: PathsConfig = PathsConfig()
    integrations: IntegrationsConfig = IntegrationsConfig()
    tools: ToolsConfig = ToolsConfig()


config = Config()
