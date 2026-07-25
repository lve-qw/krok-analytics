import numpy as np
from typing import List, Dict, Tuple
import hdbscan
from sklearn.metrics import silhouette_score
from schemas import ClusterInfo, UseCase
from prompts import NAME_CLUSTER_PROMPT
from config import config


class DialogClusterer:
    def __init__(self, llm_analyzer=None):
        self.min_cluster_size = config.clustering.min_cluster_size
        self.min_samples = config.clustering.min_samples
        self.top_n = config.clustering.top_n_for_naming
        self.llm = llm_analyzer

    def cluster(self, embeddings: np.ndarray) -> Dict[int, List[int]]:
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric='euclidean',
            cluster_selection_method='eom',
            prediction_data=True
        )
        
        labels = clusterer.fit_predict(embeddings)
        
        clusters: Dict[int, List[int]] = {}
        noise_indices = []
        
        for idx, label in enumerate(labels):
            if label == -1:
                noise_indices.append(idx)
            else:
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(idx)
        
        if noise_indices:
            max_id = max(clusters.keys()) + 1 if clusters else 0
            clusters[max_id] = noise_indices
        
        return clusters

    def get_representative_messages(
        self, 
        cluster_indices: List[int], 
        embeddings: np.ndarray, 
        messages: List[str],
        top_n: int = None
    ) -> List[str]:
        if top_n is None:
            top_n = self.top_n
        
        if len(cluster_indices) == 0:
            return []
        
        cluster_embeddings = embeddings[cluster_indices]
        centroid = np.mean(cluster_embeddings, axis=0)
        
        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        top_indices = np.argsort(distances)[:min(top_n, len(cluster_indices))]
        
        return [messages[cluster_indices[i]] for i in top_indices]

    def name_cluster(self, messages: List[str]) -> str:
        if self.llm is None:
            return self._heuristic_name(messages)
        
        messages_text = "\n".join(f"- {m}" for m in messages[:20])
        prompt = NAME_CLUSTER_PROMPT.format(messages=messages_text)
        
        try:
            import json
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            inputs = self.llm.tokenizer(prompt, return_tensors="pt").to(self.llm.device)
            
            with torch.no_grad():
                outputs = self.llm.model.generate(
                    **inputs,
                    max_new_tokens=100,
                    temperature=0.1,
                    do_sample=True,
                    pad_token_id=self.llm.tokenizer.eos_token_id
                )
            
            generated = self.llm.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
            
            try:
                generated = generated.strip()
                if generated.startswith("```"):
                    generated = generated.split("```")[1]
                    if generated.startswith("json"):
                        generated = generated[3:]
                data = json.loads(generated.strip())
                if "use_case" in data:
                    return data["use_case"]
            except:
                pass
            
            return self._heuristic_name(messages)
        except Exception as e:
            print(f"Error naming cluster with LLM: {e}")
            return self._heuristic_name(messages)

    def _heuristic_name(self, messages: List[str]) -> str:
        if not messages:
            return "Другое"
        
        sample = messages[0][:100]
        
        keywords = {
            "Письма и email": ["письмо", "email", "почта", "отправить"],
            "Задачи и проекты": ["задача", "тикет", "jira", "проект"],
            "Календарь и встречи": ["встреча", "календарь", "напоминание", "планировать"],
            "Отчеты и аналитика": ["отчет", "анализ", "данные", "crm"],
            "Документы": ["документ", "excel", "файл", "создать"],
            "Поиск информации": ["найти", "поиск", "информация", "узнать"],
            "Код и разработка": ["код", "python", "ошибка", "разработка"],
        }
        
        for name, kws in keywords.items():
            if any(kw in sample.lower() for kw in kws):
                return name
        
        return "Общий сценарий"

    def process_clusters(
        self, 
        embeddings: np.ndarray, 
        messages: List[str]
    ) -> Tuple[Dict[int, List[int]], List[UseCase]]:
        clusters = self.cluster(embeddings)
        use_cases = []
        
        for cluster_id, indices in clusters.items():
            rep_messages = self.get_representative_messages(indices, embeddings, messages)
            use_case_name = self.name_cluster(rep_messages)
            
            for idx in indices:
                use_cases.append(UseCase(
                    request_id=idx,
                    cluster_id=cluster_id,
                    use_case=use_case_name,
                    member_count=len(indices)
                ))
        
        return clusters, use_cases
