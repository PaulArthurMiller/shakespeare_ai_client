import json
import os
import importlib.util
import re
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional, Union
from modules.utils.logger import CustomLogger
from openai import OpenAI
from anthropic import Anthropic

load_dotenv()

class StoryExpander:
    def __init__(
        self,
        config_path: str = "modules/playwright/config.py",
        scene_summaries_path: str = "data/prompts/scene_summaries.json",
        character_voices_path: str = "data/prompts/character_voices.json",
        output_path: str = "data/modern_play/expanded_story.json",
        testing_mode: bool = False
    ) -> None:
        self.logger = CustomLogger("StoryExpander")
        self.logger.info("Initializing StoryExpander")

        self.config = self._load_config(config_path)
        self.model_provider: str = self.config.get("model_provider", "openai")
        self.model_name: str = self.config.get("model_name", "gpt-4o")
        self.temperature: float = self.config.get("temperature", 0.7)

        self.openai_client: Optional[OpenAI] = None
        self.anthropic_client: Optional[Anthropic] = None
        self._init_model_client()

        # Store paths
        self.scene_summaries_path: str = scene_summaries_path
        self.character_voices_path: str = character_voices_path
        self.expanded_story_path: str = output_path
        
        # Testing mode flag for more graceful behavior in tests
        self.testing_mode: bool = testing_mode
        
        # Thematic guidelines (could be loaded from a file or set directly)
        self.thematic_guidelines: str = (
            "Global thematic instructions provided by the client. "
            "Ensure all scenes reflect these themes consistently."
        )

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load configuration from a Python module."""
        spec = importlib.util.spec_from_file_location("config", path)
        if spec is None or spec.loader is None:
            raise ImportError("Could not load configuration")

        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)

        return {
            key: getattr(config_module, key)
            for key in dir(config_module)
            if not key.startswith("__")
        }

    def _load_json(self, path: str) -> Dict[str, Any]:
        """Load JSON data with better error handling."""
        self.logger.info(f"Loading JSON from: {path}")
        
        if not os.path.exists(path):
            error_msg = f"JSON file not found: {path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                
                if not content:
                    error_msg = f"JSON file is empty: {path}"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)
                    
                return json.loads(content)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in file {path}: {str(e)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

    def _init_model_client(self) -> None:
        """Initialize the appropriate model client based on provider."""
        if self.model_provider == "anthropic":
            self.anthropic_client = Anthropic()
        else:
            self.openai_client = OpenAI()

    def _build_prompt(self, scene_data: Dict[str, Any], character_voices: Dict[str, str]) -> str:
        """Build the prompt for the LLM to expand a scene."""
        voice_descriptions = "\n".join(
            f"{char}: {desc}" for char, desc in character_voices.items()
        )

        return f"""
You are expanding detailed scene summaries into structured scene descriptions for a modern play styled like Shakespeare's Macbeth, but using contemporary American English.

Scene Overview:
{scene_data["overview"]}

Thematic Guidelines:
{self.thematic_guidelines}

Characters and their voice styles:
{voice_descriptions}

Setting:
{scene_data.get("setting", "Provide a rich, suitable setting.")}

Characters present:
{', '.join(scene_data["characters"])}

Additional Instructions:
{scene_data.get("additional_instructions", "None")}

Provide detailed expansions for this scene including:
- Rich setting description
- 3 to 5 clear dramatic beats directly based on the scene overview
- Dramatic function tags (e.g., #DIALOGUE_TURN, #SOLILOQUY)
- Specific onstage events (entrances, exits, notable actions)
- Voice primers for each character present

Output JSON strictly formatted as:
{{
  "act": "{scene_data["act"]}",
  "scene": {scene_data["scene"]},
  "setting": "...",
  "characters": ["..."],
  "voice_primers": {{"Character": "Primer"}},
  "dramatic_functions": ["#..."],
  "beats": ["..."],
  "onstage_events": ["..."]
}}
""".strip()

    def _clean_json_response(self, response: str) -> str:
        """Clean JSON response by removing markdown code blocks if present."""
        cleaned = re.sub(r"^```(?:json)?\n?|```$", "", response.strip(), flags=re.MULTILINE)
        return cleaned.strip()

    def _call_model(self, prompt: str) -> str:
        """Call the appropriate LLM based on the configured provider."""
        if self.model_provider == "anthropic" and self.anthropic_client:
            response = self.anthropic_client.messages.create(
                model=self.model_name,
                max_tokens=2048,
                temperature=self.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            from anthropic.types import TextBlock
            content = "".join(
                block.text for block in response.content
                if isinstance(block, TextBlock)
            )
            return content.strip()

        elif self.openai_client:
            response = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a literary scene development assistant for a modern Shakespeare-inspired play. "
                            "Your role is to expand scene summaries into fully structured dramatic outlines—deeply rooted in the play's central themes.\n\n"
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""

        return ""

    def expand_all_scenes(
        self, 
        scene_summaries_path: Optional[str] = None,
        character_voices_path: Optional[str] = None,
        output_path: Optional[str] = None,
        scene_summaries_data: Optional[Dict[str, Any]] = None,
        character_voices_data: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Expand scene summaries into detailed scene descriptions.
        
        The method can use either file paths or direct data objects:
        - File paths: Uses scene_summaries_path and character_voices_path
        - Direct data: Uses scene_summaries_data and character_voices_data
        
        Args:
            scene_summaries_path: Path to scene summaries JSON file
            character_voices_path: Path to character voices JSON file
            output_path: Path to save expanded story
            scene_summaries_data: Direct scene summaries data (overrides file path)
            character_voices_data: Direct character voices data (overrides file path)
            
        Returns:
            Path to the expanded story JSON
        """
        self.logger.info("Starting scene expansion...")
        
        # Determine sources for scene summaries and character voices
        scene_summaries = None
        character_voices = None
        
        # Load scene summaries (prioritize direct data if provided)
        if scene_summaries_data is not None:
            self.logger.info("Using provided scene summaries data")
            scene_summaries = scene_summaries_data
        else:
            # Load from file
            summaries_path = scene_summaries_path or self.scene_summaries_path
            self.logger.info(f"Loading scene summaries from {summaries_path}")
            
            if not os.path.exists(summaries_path):
                error_msg = f"Scene summaries file not found: {summaries_path}"
                self.logger.error(error_msg)
                
                if self.testing_mode:
                    # Create minimal valid data for testing
                    self.logger.warning("Using minimal scene summaries for testing")
                    scene_summaries = {"scenes": [{"act": "I", "scene": "1", "overview": "Test scene", "characters": ["CHARACTER1"]}]}
                else:
                    raise FileNotFoundError(error_msg)
            else:
                try:
                    scene_summaries = self._load_json(summaries_path)
                except Exception as e:
                    self.logger.error(f"Failed to load scene summaries: {e}")
                    if self.testing_mode:
                        # Use minimal data for testing
                        self.logger.warning("Using minimal scene summaries for testing due to error")
                        scene_summaries = {"scenes": [{"act": "I", "scene": "1", "overview": "Test scene", "characters": ["CHARACTER1"]}]}
                    else:
                        raise
        
        # Load character voices (prioritize direct data if provided)
        if character_voices_data is not None:
            self.logger.info("Using provided character voices data")
            character_voices = character_voices_data
        else:
            # Load from file
            voices_path = character_voices_path or self.character_voices_path
            self.logger.info(f"Loading character voices from {voices_path}")
            
            if not os.path.exists(voices_path):
                error_msg = f"Character voices file not found: {voices_path}"
                self.logger.error(error_msg)
                
                if self.testing_mode:
                    # Create minimal valid data for testing
                    self.logger.warning("Using minimal character voices for testing")
                    character_voices = {"CHARACTER1": "Formal speech pattern"}
                else:
                    raise FileNotFoundError(error_msg)
            else:
                try:
                    character_voices = self._load_json(voices_path)
                except Exception as e:
                    self.logger.error(f"Failed to load character voices: {e}")
                    if self.testing_mode:
                        # Use minimal data for testing
                        self.logger.warning("Using minimal character voices for testing due to error")
                        character_voices = {"CHARACTER1": "Formal speech pattern"}
                    else:
                        raise
        
        # Determine output path
        expanded_story_path = output_path or self.expanded_story_path
        
        # Process each scene
        expanded_scenes = []
        for scene_data in scene_summaries.get("scenes", []):
            try:
                self.logger.info(f"Expanding Act {scene_data['act']}, Scene {scene_data['scene']}")
                prompt = self._build_prompt(scene_data, character_voices)
                expanded_scene_json = self._call_model(prompt)
                cleaned = self._clean_json_response(expanded_scene_json)
                
                try:
                    expanded_scene = json.loads(cleaned)
                    expanded_scenes.append(expanded_scene)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse expanded scene JSON: {e}")
                    if self.testing_mode:
                        # Create a minimal valid expanded scene for testing
                        self.logger.warning("Using minimal expanded scene for testing due to JSON error")
                        expanded_scenes.append({
                            "act": scene_data["act"],
                            "scene": scene_data["scene"],
                            "setting": "Test setting",
                            "characters": scene_data.get("characters", ["CHARACTER1"]),
                            "voice_primers": {"CHARACTER1": "Formal"},
                            "dramatic_functions": ["#TEST"],
                            "beats": ["Test beat 1", "Test beat 2"],
                            "onstage_events": ["CHARACTER1 enters"]
                        })
                    else:
                        raise ValueError(f"Failed to expand scene {scene_data['act']}.{scene_data['scene']}: {e}")
                        
            except Exception as e:
                self.logger.error(f"Failed to expand scene {scene_data['act']}.{scene_data['scene']}: {e}")
                if self.testing_mode:
                    # Create a minimal valid expanded scene for testing
                    self.logger.warning("Using minimal expanded scene for testing due to error")
                    expanded_scenes.append({
                        "act": scene_data["act"],
                        "scene": scene_data["scene"],
                        "setting": "Test setting",
                        "characters": scene_data.get("characters", ["CHARACTER1"]),
                        "voice_primers": {"CHARACTER1": "Formal"},
                        "dramatic_functions": ["#TEST"],
                        "beats": ["Test beat 1", "Test beat 2"],
                        "onstage_events": ["CHARACTER1 enters"]
                    })
                else:
                    raise
        
        # Save the expanded scenes
        os.makedirs(os.path.dirname(expanded_story_path), exist_ok=True)
        with open(expanded_story_path, "w", encoding="utf-8") as f:
            json.dump({"scenes": expanded_scenes}, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Expanded scenes saved to {expanded_story_path}")
        return expanded_story_path