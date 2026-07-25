import asyncio
from pathlib import Path
from tqdm import tqdm
from config import config
from parser import DialogParser
from token_counter import TokenCounter
from llm import LLMAnalyzer
from zero_shot_classifier import ZeroShotClassifier
from embeddings import TextEmbedder
from clustering import DialogClusterer
from utils import (
    save_dialogs_csv, 
    save_use_cases_csv, 
    save_analytics_csv, 
    load_classes, 
    ensure_dirs
)
from schemas import DialogAnalysis, DialogMetadata, ClassificationResult, TokenCounts


def run_pipeline(dialogs_dir: Path = None, outputs_dir: Path = None):
    if dialogs_dir is None:
        dialogs_dir = config.paths.dialogs_dir
    if outputs_dir is None:
        outputs_dir = config.paths.outputs_dir
    
    ensure_dirs([outputs_dir, config.paths.models_dir])
    
    print("=" * 50)
    print("ЗАПУСК PIPELINE АНАЛИЗА ДИАЛОГОВ")
    print("=" * 50)
    
    print("\n[1/6] Загрузка данных...")
    parser = DialogParser(dialogs_dir)
    dialogs = parser.parse_all()
    print(f"Загружено {len(dialogs)} диалогов")
    
    if not dialogs:
        print("Нет диалогов для обработки!")
        return
    
    print("\n[2/6] Загрузка классов...")
    classes = load_classes(config.paths.classes_file)
    print(f"Загружено {len(classes)} классов: {[name for _, name in classes]}")
    
    print("\n[3/6] Инициализация моделей...")
    token_counter = TokenCounter()
    
    print("\n--- LLM Analyzer ---")
    llm_analyzer = LLMAnalyzer()
    
    print("\n--- Zero-Shot Classifier ---")
    classifier = ZeroShotClassifier(classes)
    
    print("\n--- Text Embedder ---")
    embedder = TextEmbedder()
    
    print("\n[4/6] Анализ диалогов (LLM + Zero-Shot)...")
    analyses = []
    
    for dialog in tqdm(dialogs, desc="Анализ диалогов"):
        first_msg = parser.get_first_user_message(dialog)
        dialog_text = parser.get_dialog_text(dialog)
        
        metadata = llm_analyzer.analyze_dialog(dialog)
        # Классифицируем только первое сообщение пользователя (не весь диалог)
        classification = classifier.classify(first_msg)
        token_counts = token_counter.count_messages(dialog.messages)
        
        # Определяем статус анализа
        analysis_status = "parse_error" if metadata.failure_reason == "LLM parse error" else "success"
        metadata_confidence = 0.0 if analysis_status == "parse_error" else 1.0
        
        analysis = DialogAnalysis(
            request_id=dialog.id,
            dialog_id=dialog.id,
            user_id=dialog.user_id,
            created_at=dialog.created_at,
            first_user_message=first_msg,
            metadata=metadata,
            classification=classification,
            token_counts=token_counts,
            class_labels=classification.class_names,
            analysis_status=analysis_status,
            metadata_confidence=metadata_confidence
        )
        analyses.append(analysis)
    
    dialogs_csv_path = outputs_dir / "dialogs.csv"
    save_dialogs_csv(analyses, dialogs_csv_path)
    
    print("\n[5/6] Кластеризация и именование use cases...")
    messages = [a.first_user_message for a in analyses]
    embeddings = embedder.embed_batch(messages, show_progress=True)
    
    clusterer = DialogClusterer(llm_analyzer)
    request_ids = [a.request_id for a in analyses]
    clusters, use_cases = clusterer.process_clusters(embeddings, messages, request_ids)
    
    print(f"Найдено {len(clusters)} кластеров")
    for cid, indices in sorted(clusters.items()):
        print(f"  Кластер {cid}: {len(indices)} диалогов")
    
    use_cases_csv_path = outputs_dir / "use_cases.csv"
    save_use_cases_csv(use_cases, use_cases_csv_path)
    
    print("\n[6/6] Создание итогового dataset...")
    analytics_csv_path = outputs_dir / "analytics.csv"
    analytics_df = save_analytics_csv(dialogs_csv_path, use_cases_csv_path, analytics_csv_path)
    
    print("\n" + "=" * 50)
    print("PIPELINE ЗАВЕРШЕН")
    print("=" * 50)
    print(f"\nВыходные файлы:")
    print(f"  - {dialogs_csv_path}")
    print(f"  - {use_cases_csv_path}")
    print(f"  - {analytics_csv_path}")
    
    print(f"\nСтатистика:")
    print(f"  - Диалогов обработано: {len(analyses)}")
    print(f"  - Кластеров найдено: {len(clusters)}")
    print(f"  - Рабочих запросов: {sum(1 for a in analyses if a.metadata.is_work)}")
    print(f"  - Кандидатов на автоматизацию: {sum(1 for a in analyses if a.metadata.automation_candidate)}")
    
    return analytics_df


if __name__ == "__main__":
    run_pipeline()
