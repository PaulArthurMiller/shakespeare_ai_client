# modules/translator/scene_saver.py

import os
import json
from typing import List, Dict, Any, Optional
from modules.utils.logger import CustomLogger
from modules.translator.config import get_output_dir

class SceneSaver:
    def __init__(self, translation_id: Optional[str] = None, base_output_dir: str = "outputs/translated_scenes"):
        self.logger = CustomLogger("SceneSaver")
        
        if translation_id:
            self.output_dir = get_output_dir(translation_id)
        else:
            self.output_dir = base_output_dir
            
        os.makedirs(self.output_dir, exist_ok=True)

    def save_scene(
        self,
        act: str,
        scene: str,
        translated_lines: List[Dict[str, Any]],
        original_lines: Optional[List[str]] = None,
        checkpoint_interval: int = 5
    ):
        """
        Save the translated scene incrementally.
        - act and scene are string identifiers.
        - translated_lines is a list of line dictionaries with 'text', 'references', etc.
        - original_lines is an optional list of the original modern lines (if available)
        """
        # Remove any underscores in the act before adding it to the template
        clean_act = act.lower().strip('_')
        scene_id = f"act_{clean_act}_scene_{scene}"
        json_path = os.path.join(self.output_dir, f"{scene_id}.json")
        md_path = os.path.join(self.output_dir, f"{scene_id}.md")

        # If original_lines is not provided, we'll extract what we can from translated_lines
        if original_lines is None:
            # See if original modern lines are stored within the translated lines
            original_lines = []
            for line_data in translated_lines:
                if "original_modern_line" in line_data:
                    original_lines.append(line_data["original_modern_line"])
                else:
                    # If not available, we'll use empty strings as placeholders
                    original_lines.append("")

        # Ensure the lists are the same length
        if len(original_lines) < len(translated_lines):
            original_lines.extend([""] * (len(translated_lines) - len(original_lines)))
        elif len(original_lines) > len(translated_lines):
            original_lines = original_lines[:len(translated_lines)]

        # Enhance the translated_lines with original lines
        enhanced_lines = []
        for i, line_data in enumerate(translated_lines):
            # Create a copy to avoid modifying the original
            enhanced_line = line_data.copy()
            
            # Add the original modern line
            if not enhanced_line.get("original_modern_line"):
                enhanced_line["original_modern_line"] = original_lines[i]
            
            # Format quoted references for display
            quoted_refs = []
            for ref in enhanced_line.get("references", []):
                source = ref.get("title", "Unknown")
                act_num = ref.get("act", "")
                scene_num = ref.get("scene", "")
                line_num = ref.get("line", "")
                
                # Format the reference
                ref_str = f"{source} ({act_num}.{scene_num}.{line_num})"
                quoted_refs.append(ref_str)
            
            enhanced_line["formatted_references"] = quoted_refs
            enhanced_lines.append(enhanced_line)

        # Save in batches for checkpointing
        accumulated = []
        for idx, enhanced_line in enumerate(enhanced_lines, start=1):
            accumulated.append(enhanced_line)

            if idx % checkpoint_interval == 0 or idx == len(enhanced_lines):
                self.logger.info(f"Checkpoint: Saving line {idx} of scene {scene_id}")
                self._save_json(json_path, act, scene, accumulated, original_lines[:idx])
                self._save_md(md_path, act, scene, accumulated)

    def _save_json(self, path: str, act: str, scene: str, lines: List[Dict[str, Any]], original_lines: Optional[List[str]] = None):
        """
        Save the complete scene data to a JSON file with rich metadata.
        """
        # Create a comprehensive scene data structure
        data = {
            "act": act,
            "scene": scene,
            "metadata": {
                "timestamp": self._get_timestamp(),
                "total_lines": len(lines),
                "has_original_lines": original_lines is not None and any(original_lines)
            },
            "translated_lines": lines
        }
        
        # Add original lines array if available
        if original_lines:
            data["original_lines"] = original_lines
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved JSON scene to {path}")
        except Exception as e:
            self.logger.error(f"Error saving JSON scene to {path}: {e}")

    def _save_md(self, path: str, act: str, scene: str, lines: List[Dict[str, Any]]):
        """
        Save a simple markdown preview of the scene.
        This is just for quick reference - a dedicated formatter will be needed 
        for the final output.
        """
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# ACT {act}\n\n## SCENE {scene}\n\n")
                f.write("| Shakespearean Line | References | Modern Line |\n")
                f.write("|-------------------|------------|-------------|\n")
                
                for line in lines:
                    shakespeare_text = line.get("text", "").replace("\n", " ")
                    refs = ", ".join(line.get("formatted_references", []))
                    modern_text = line.get("original_modern_line", "").replace("\n", " ")
                    
                    # Escape pipe characters for markdown tables
                    shakespeare_text = shakespeare_text.replace("|", "\\|")
                    refs = refs.replace("|", "\\|")
                    modern_text = modern_text.replace("|", "\\|")
                    
                    f.write(f"| {shakespeare_text} | {refs} | {modern_text} |\n")
                    
            self.logger.debug(f"Saved Markdown scene to {path}")
        except Exception as e:
            self.logger.error(f"Error saving Markdown scene to {path}: {e}")
    
    def _get_timestamp(self):
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()