# Note: Scene adjustment functionality is experimental and not currently 
# connected to the UI. This can be activated for future development if needed.

import os
import json
from typing import Dict, Any, Optional
from modules.utils.logger import CustomLogger
from openai import OpenAI
from anthropic import Anthropic
import importlib.util

class ArtisticAdjuster:
    def __init__(
        self,
        config_path: str = "modules/playwright/config.py",
        model_override: Optional[str] = None
    ):
        self.logger = CustomLogger("ArtisticAdjuster")
        self.logger.info("Initializing ArtisticAdjuster")

        self.config = self._load_config(config_path)
        self.model_provider = self.config.get("model_provider", "openai")
        self.model_name = model_override or self.config.get("model_name", "gpt-4o")
        self.temperature = self.config.get("temperature", 0.7)

        self.openai_client: Optional[OpenAI] = None
        self.anthropic_client: Optional[Anthropic] = None
        self._init_model_client()

    def _load_config(self, path: str) -> Dict[str, Any]:
        spec = importlib.util.spec_from_file_location("config", path)
        if spec is None or spec.loader is None:
            raise ImportError("Could not load config")

        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)  # type: ignore[attr-defined]

        return {
            key: getattr(config_module, key)
            for key in dir(config_module)
            if not key.startswith("__")
        }

    def _init_model_client(self):
        if self.model_provider == "anthropic":
            self.logger.info("Using Anthropic client")
            self.anthropic_client = Anthropic()
        else:
            self.logger.info("Using OpenAI client")
            self.openai_client = OpenAI()

    def _build_prompt(self, script_text: str, critique: str) -> str:
        return f"""
You are an artistic script adjuster. Your task is to minimally revise the following play scene to address a specific critique while preserving its structure, tone, and emotional arc. Do not rewrite the scene wholesale. Make only the changes required to satisfy the critique. Length and quality must be maintained.

Critique:
"{critique}"

Play Scene:
{script_text}

Please return the adjusted play scene in the same format, with stage directions and character names preserved. Only make necessary changes.
"""

    def revise_scene(self, scene_path: str, critique: str, output_dir: Optional[str] = None) -> str:
        with open(scene_path, "r", encoding="utf-8") as f:
            script_text = f.read()

        prompt = self._build_prompt(script_text, critique)

        if self.model_provider == "anthropic" and self.anthropic_client is not None:
            response = self.anthropic_client.messages.create(
                model=self.model_name,
                max_tokens=3000,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            from anthropic.types import TextBlock
            content = "".join(
                block.text for block in response.content
                if isinstance(block, TextBlock)
            ).strip()
        elif self.openai_client is not None:
            response = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a skilled script editor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature
            )
            content = response.choices[0].message.content.strip() if response.choices and response.choices[0].message and response.choices[0].message.content else ""
        else:
            raise RuntimeError("No valid model client initialized")

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            basename = os.path.basename(scene_path)
            base_name_no_ext = os.path.splitext(basename)[0]
            v2_name = f"{base_name_no_ext}_v2"

            md_path = os.path.join(output_dir, f"{v2_name}.md")
            json_path = os.path.join(output_dir, f"{v2_name}.json")

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.logger.info(f"Revised scene saved to {md_path}")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump({"script": content}, f, indent=2)
            self.logger.info(f"Revised scene JSON saved to {json_path}")

        return content

if __name__ == "__main__":
    adjuster = ArtisticAdjuster()
    adjusted = adjuster.revise_scene(
        scene_path="data/modern_play/generated_scenes_claude2/act_v_scene_2.md",
        critique="The final image should include the Djinn's childlike voice echoing one last time: 'Who’s there?' — suggesting that humanity's cycle of ambition and failure is not over.",
        output_dir="data/modern_play/final_edits"
    )
    print(adjusted)
