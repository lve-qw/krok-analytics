import json
import torch
from typing import List, Optional
from schemas import Dialog, MessageClassification, MessageClassificationResult
from prompts import CLASSIFY_MESSAGES_PROMPT
from config import config


class MessageClassifier:
    def __init__(self, model=None, tokenizer=None, device=None):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        
        if model is None or tokenizer is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            print(f"Loading model for message classification: {config.models.llm_model}...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                config.models.llm_model,
                cache_dir=str(config.paths.models_dir)
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                config.models.llm_model,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
                cache_dir=str(config.paths.models_dir)
            )
            if device and device != "cuda":
                self.model = self.model.to(device)
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
            print("Message classifier loaded successfully")

    def _format_dialog(self, dialog: Dialog) -> str:
        """Форматируем диалог для промпта."""
        lines = []
        for i, msg in enumerate(dialog.messages):
            if msg.role == "user":
                lines.append(f"[{i}] User: {msg.content}")
            elif msg.role == "assistant":
                lines.append(f"[{i}] Agent: {msg.content}")
            elif msg.role == "tool":
                tool_info = f"{msg.tool_name}({json.dumps(msg.arguments) if msg.arguments else ''})"
                result_info = json.dumps(msg.result) if msg.result else ""
                lines.append(f"[{i}] Tool: {tool_info} → {result_info}")
        return "\n".join(lines)

    def classify_dialog(self, dialog: Dialog) -> MessageClassificationResult:
        """Классифицирует все сообщения агента в диалоге."""
        dialog_text = self._format_dialog(dialog)
        prompt = CLASSIFY_MESSAGES_PROMPT.format(dialog_text=dialog_text)
        
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=500,
                    temperature=0.1,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            generated = self.tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:], 
                skip_special_tokens=True
            ).strip()
            
            # Парсим JSON из ответа
            classifications = self._parse_response(generated, dialog.messages)
            
            # Считаем burned_tokens
            burned_tokens = 0
            useful_count = 0
            useless_count = 0
            
            for cls in classifications:
                if cls.is_useful:
                    useful_count += 1
                else:
                    useless_count += 1
                    # Считаем токены бесполезного сообщения
                    msg = dialog.messages[cls.message_index]
                    if msg.role == "assistant":
                        burned_tokens += self._count_tokens(msg.content)
                    elif msg.role == "tool":
                        tool_text = json.dumps(msg.arguments or {}) + json.dumps(msg.result or {})
                        burned_tokens += self._count_tokens(tool_text)
            
            return MessageClassificationResult(
                messages=classifications,
                burned_tokens=burned_tokens,
                total_messages=len(classifications),
                useful_count=useful_count,
                useless_count=useless_count
            )
            
        except Exception as e:
            print(f"Error classifying messages: {e}")
            return MessageClassificationResult(
                messages=[],
                burned_tokens=0,
                total_messages=0,
                useful_count=0,
                useless_count=0
            )

    def _parse_response(self, response: str, messages: List) -> List[MessageClassification]:
        """Парсит JSON ответ от модели."""
        classifications = []
        
        # Очищаем ответ от markdown
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1].strip()
            if response.startswith("json"):
                response = response[3:].strip()
        
        try:
            data = json.loads(response)
            if isinstance(data, list):
                for item in data:
                    if "message_index" in item and "is_useful" in item:
                        classifications.append(MessageClassification(
                            message_index=item.get("message_index", 0),
                            role=item.get("role", "assistant"),
                            is_useful=item.get("is_useful", True),
                            reason=item.get("reason", "other")
                        ))
        except json.JSONDecodeError:
            # Пробуем найти JSON в тексте
            import re
            json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    for item in data:
                        if "message_index" in item and "is_useful" in item:
                            classifications.append(MessageClassification(
                                message_index=item.get("message_index", 0),
                                role=item.get("role", "assistant"),
                                is_useful=item.get("is_useful", True),
                                reason=item.get("reason", "other")
                            ))
                except:
                    pass
        
        # Если не распарсилось, возвращаем пустой список
        return classifications

    def _count_tokens(self, text: str) -> int:
        """Считает токены в тексте."""
        if not text:
            return 0
        try:
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            return len(encoder.encode(text))
        except:
            return len(text) // 4  # Грубая оценка

    def classify_batch(self, dialogs: List[Dialog]) -> List[MessageClassificationResult]:
        """Классифицирует сообщения в нескольких диалогах."""
        return [self.classify_dialog(dialog) for dialog in dialogs]
