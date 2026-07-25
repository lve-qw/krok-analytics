import json
import torch
from typing import List, Optional
from transformers import AutoModelForCausalLM, AutoTokenizer
from schemas import Dialog, DialogMetadata
from prompts import ANALYZE_DIALOG_PROMPT
from config import config


class LLMAnalyzer:
    def __init__(self):
        self.model_name = config.models.llm_model
        self.device = self._get_device()
        print(f"Loading LLM: {self.model_name} on {self.device}...")
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=config.paths.models_dir,
            trust_remote_code=True
        )
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            cache_dir=config.paths.models_dir,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True
        )
        
        if self.device != "cuda":
            self.model = self.model.to(self.device)
        
        print("LLM loaded successfully")

    def _get_device(self) -> str:
        if config.models.device == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif config.models.device == "cpu":
            return "cpu"
        else:
            return "cuda" if torch.cuda.is_available() else "cpu"

    def analyze_dialog(self, dialog: Dialog) -> DialogMetadata:
        dialog_text = self._format_dialog_truncated(dialog, max_tokens=28000)
        prompt = ANALYZE_DIALOG_PROMPT.format(dialog_text=dialog_text)
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=config.models.temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        generated_text = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        metadata = self._parse_response(generated_text)
        
        if not metadata:
            metadata = self._get_default_metadata()
        
        return metadata

    def _format_dialog(self, dialog: Dialog) -> str:
        parts = []
        for msg in dialog.messages:
            parts.append(f"{msg.role.upper()}: {msg.content}")
        return "\n\n".join(parts)

    def _format_dialog_truncated(self, dialog: Dialog, max_tokens: int = 28000) -> str:
        parts = []
        current_tokens = 0
        
        for i, msg in enumerate(dialog.messages):
            msg_tokens = len(self.tokenizer.encode(msg.content))
            if current_tokens + msg_tokens > max_tokens and i > 10:
                parts.append(f"... [ещё {len(dialog.messages) - i} сообщений обрезано из-за ограничения длины] ...")
                break
            parts.append(f"{msg.role.upper()}: {msg.content}")
            current_tokens += msg_tokens
        
        return "\n\n".join(parts)

    def _parse_response(self, response: str) -> Optional[DialogMetadata]:
        try:
            response = response.strip()
            
            if not response:
                print("Warning: Empty LLM response")
                return None
            
            if response.startswith("```"):
                parts = response.split("```")
                response = parts[1] if len(parts) > 1 else response
                if response.startswith("json"):
                    response = response[3:]
            
            response = response.strip()
            
            data = json.loads(response)
            return DialogMetadata(
                summary=data.get("summary", ""),
                goal=data.get("goal", ""),
                intent=data.get("intent", ""),
                is_work=data.get("is_work", False),
                automation_candidate=data.get("automation_candidate", False),
                periodicity=data.get("periodicity", "none"),
                complexity=data.get("complexity", "simple"),
                steps_requested=data.get("steps_requested", 1),
                integrations=data.get("integrations", []),
                integration_count=len(data.get("integrations", [])),
                tools=data.get("tools", []),
                tool_calls=data.get("tool_calls", 0),
                uses_company_data=data.get("uses_company_data", False),
                company_sources=data.get("company_sources", []),
                requires_generation=data.get("requires_generation", []),
                search_type=data.get("search_type", []),
                contains_sensitive_data=data.get("contains_sensitive_data", False),
                prompt_injection=data.get("prompt_injection", False),
                agent_failed=data.get("agent_failed", False),
                failure_reason=data.get("failure_reason"),
                language=data.get("language", "ru")
            )
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error parsing LLM response: {e}")
            print(f"Raw response: {response[:500] if response else 'EMPTY'}")
            return None

    def _get_default_metadata(self) -> DialogMetadata:
        return DialogMetadata(
            summary="",
            goal="",
            intent="",
            is_work=True,
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

    def analyze_batch(self, dialogs: List[Dialog]) -> List[DialogMetadata]:
        return [self.analyze_dialog(dialog) for dialog in dialogs]
