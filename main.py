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
from message_classifier import MessageClassifier
from utils import (
    save_dialogs_csv, 
    save_use_cases_csv, 
    save_analytics_csv, 
    load_classes, 
    ensure_dirs
)
from dashboard_generator import generate_dashboard
from schemas import DialogAnalysis, DialogMetadata, ClassificationResult, TokenCounts


def run_pipeline(dialogs_dir: Path = None, outputs_dir: Path = None, skip_llm: bool = False):
    if dialogs_dir is None:
        dialogs_dir = config.paths.dialogs_dir
    if outputs_dir is None:
        outputs_dir = config.paths.outputs_dir
    
    ensure_dirs([outputs_dir, config.paths.models_dir])
    
    print("=" * 50)
    print("ЗАПУСК PIPELINE АНАЛИЗА ДИАЛОГОВ")
    print("=" * 50)
    
    if skip_llm:
        print("\n!!! РЕЖИМ БЫСТРОЙ КЛАСТЕРИЗАЦИИ (LLM и классификация пропущены) !!!")
    
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
    
    llm_analyzer = None
    classifier = None
    
    if not skip_llm:
        print("\n--- LLM Analyzer ---")
        llm_analyzer = LLMAnalyzer()
        
        print("\n--- Zero-Shot Classifier ---")
        classifier = ZeroShotClassifier(classes)
    else:
        print("\n[SKIP] LLM Analyzer и Zero-Shot Classifier пропущены")
    
    print("\n--- Text Embedder ---")
    embedder = TextEmbedder()
    
    print("\n[4/6] Анализ диалогов..." + ("(только токены)" if skip_llm else "(LLM + Zero-Shot)..."))
    analyses = []
    
    for dialog in tqdm(dialogs, desc="Обработка диалогов"):
        first_msg = parser.get_first_user_message(dialog)
        dialog_text = parser.get_dialog_text(dialog)
        token_counts = token_counter.count_messages(dialog.messages)
        
        if skip_llm:
            # Создаём пустые метаданные без LLM
            from schemas import DialogMetadata, ClassificationResult
            metadata = DialogMetadata(
                summary="",
                goal="",
                intent="",
                is_work=False,
                automation_candidate=False,
                periodicity="none",
                complexity="simple",
                steps_requested=1,
                integrations=[],
                integration_count=0,
                tools=[],
                tool_calls=0,
                uses_company_data=False,
                company_sources=[],
                requires_generation=[],
                search_type=[],
                contains_sensitive_data=False,
                prompt_injection=False,
                agent_failed=False,
                failure_reason=None,
                language="ru"
            )
            classification = ClassificationResult(
                class_ids=[],
                class_names=[],
                scores=[],
                confidence=0.0
            )
            analysis_status = "skipped"
            metadata_confidence = 0.0
        else:
            metadata = llm_analyzer.analyze_dialog(dialog)
            classification = classifier.classify(first_msg)
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
    
    # [4.5/6] Классификация сообщений агента (полезное/бесполезное)
    if not skip_llm:
        print("\n[4.5/6] Классификация сообщений агента (LLM)...")
        msg_classifier = MessageClassifier(
            model=llm_analyzer.model,
            tokenizer=llm_analyzer.tokenizer,
            device=llm_analyzer.device
        )
        
        for analysis in tqdm(analyses, desc="Классификация сообщений"):
            # Находим оригинальный диалог
            dialog = next((d for d in dialogs if d.id == analysis.request_id), None)
            if dialog:
                msg_result = msg_classifier.classify_dialog(dialog)
                analysis.message_classification = msg_result
                analysis.burned_tokens = msg_result.burned_tokens
    
    dialogs_csv_path = outputs_dir / "dialogs.csv"
    save_dialogs_csv(analyses, dialogs_csv_path)
    
    print("\n[5/6] Кластеризация и именование use cases...")
    messages = [a.first_user_message for a in analyses]
    embeddings = embedder.embed_batch(messages, show_progress=True)
    
    # Передаём llm_analyzer только если не skip_llm, иначе кластеризация без LLM-именования
    clusterer = DialogClusterer(llm_analyzer if not skip_llm else None)
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
    
    print("\n[7/7] Генерация Dashboard...")
    report_path = outputs_dir / "report.html"
    generate_dashboard(analytics_csv_path, report_path)
    print(f"  - {report_path}")
    
    print(f"\nСтатистика:")
    print(f"  - Диалогов обработано: {len(analyses)}")
    print(f"  - Кластеров найдено: {len(clusters)}")
    if not skip_llm:
        print(f"  - Рабочих запросов: {sum(1 for a in analyses if a.metadata.is_work)}")
        print(f"  - Кандидатов на автоматизацию: {sum(1 for a in analyses if a.metadata.automation_candidate)}")
        total_burned = sum(a.burned_tokens for a in analyses)
        print(f"  - Сожжено токенов (burned): {total_burned}")
        print(f"  - Диалогов с бесполезными сообщениями: {sum(1 for a in analyses if a.burned_tokens > 0)}")
    else:
        print(f"  - LLM анализ пропущен (режим быстрой кластеризации)")
    
    return analytics_df


if __name__ == "__main__":
    import sys
    # python main.py --skip-llm для быстрой кластеризации
    skip_llm = "--skip-llm" in sys.argv
    run_pipeline(skip_llm=skip_llm)
