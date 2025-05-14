# modules/rag/used_map.py

import os
import json
from typing import Optional, Dict, Set, List, Union
from modules.utils.logger import CustomLogger

class UsedMap:
    def __init__(self, storage_dir: str = "data/used_maps/", logger: Optional[CustomLogger] = None):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.logger = logger or CustomLogger("UsedMap")
        self.active_translation_id: Optional[str] = None
        self.used_maps: Dict[str, Dict[str, Set[str]]] = {}  # translationID -> {reference_key -> set(context_ranges)}

    def _get_filepath(self, translation_id: str) -> str:
        return os.path.join(self.storage_dir, f"{translation_id}_used_map.json")

    def load(self, translation_id: str) -> None:
        """Load the used map for a given translation ID."""
        self.active_translation_id = translation_id
        path = self._get_filepath(translation_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.used_maps[translation_id] = {
                    k: set(v) for k, v in data.items()
                }
                self.logger.info(f"Loaded used map for translationID '{translation_id}' from {path}")
            except Exception as e:
                self.logger.warning(f"Failed to load used map for '{translation_id}': {e}")
                self.used_maps[translation_id] = {}
        else:
            self.logger.info(f"No existing used map for '{translation_id}' found. Starting new map.")
            self.used_maps[translation_id] = {}

    def save(self, translation_id: Optional[str] = None) -> None:
        """Save the used map for the current or specified translation ID."""
        tid = translation_id or self.active_translation_id
        if not tid:
            self.logger.error("No translation ID set for saving used map.")
            return

        path = self._get_filepath(tid)
        try:
            serializable_map = {
                k: list(v) for k, v in self.used_maps.get(tid, {}).items()
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(serializable_map, f, indent=2)
            self.logger.info(f"Used map for translationID '{tid}' saved to {path}")
        except Exception as e:
            self.logger.error(f"Failed to save used map for '{tid}': {e}")

    def mark_used(self, reference_key: str, context_range: Union[str, List[int]]) -> None:
        """Mark a chunk reference+range as used for the current translation."""
        tid = self.active_translation_id
        if not tid:
            self.logger.error("Cannot mark used: No translation ID set.")
            return

        # Convert context_range to a string regardless of its original type
        if isinstance(context_range, list):
            context_str = ",".join(str(i) for i in context_range)
        else:
            context_str = str(context_range)  # Ensure it's a string
        
        map_for_tid = self.used_maps.setdefault(tid, {})
        contexts = map_for_tid.setdefault(reference_key, set())
        if context_str not in contexts:
            contexts.add(context_str)
            self.logger.debug(f"Marked used: [{reference_key}] -> {context_str}")

    def was_used(self, reference_key: str, context_range: Union[str, List[int]]) -> bool:
        """Check if a reference+range is already used in the current translation."""
        tid = self.active_translation_id
        if not tid:
            self.logger.warning("No translation ID set; assuming not used.")
            return False
        
        # Convert to string for comparison
        if isinstance(context_range, list):
            context_str = ",".join(str(i) for i in context_range)
        else:
            context_str = str(context_range)
        
        return context_str in self.used_maps.get(tid, {}).get(reference_key, set())

    def reset(self, translation_id: Optional[str] = None) -> None:
        """Clear the used map for the specified or current translation ID."""
        tid = translation_id or self.active_translation_id
        if tid:
            self.used_maps[tid] = {}
            self.logger.info(f"Reset used map for translationID '{tid}'")
        else:
            self.logger.warning("No translation ID provided for reset.")

    def get_used_map(self, translation_id: Optional[str] = None) -> Dict[str, Set[str]]:
        """Return the used map for a given translation ID (or current one)."""
        tid = translation_id or self.active_translation_id
        if not tid:
            self.logger.warning("No translation ID set when requesting used map.")
            return {}

        return self.used_maps.setdefault(tid, {})

