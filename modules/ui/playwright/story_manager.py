"""
Story Manager for Shakespeare AI.

This module handles story-related operations, including managing 
character voices and scene summaries for story expansion.
"""
import os
import json
import time
from typing import Dict, List, Any, Optional, Tuple

from modules.ui.file_helper import (
    load_json_from_file,
    save_json_to_file,
    ensure_directory
)

# Check if core playwright modules are available
try:
    from modules.playwright.story_expander import StoryExpander
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class StoryManager:
    """
    Handles story-related operations for the Shakespeare AI playwright.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the story manager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger
        self.characters_path = "data/prompts/character_voices.json"
        self.expanded_story_path = "data/modern_play/expanded_story.json"
        
        # Ensure directories exist
        ensure_directory("data/prompts")
        ensure_directory("data/modern_play")
    
    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the provided logger if available."""
        if self.logger:
            if hasattr(self.logger, "_log"):
                self.logger._log(message, level)
            elif hasattr(self.logger, level):
                getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def save_character_voices(self, character_voices: Dict[str, str], 
                             session_folder: Optional[str] = None) -> bool:
        """
        Save character voices to JSON.
        
        Args:
            character_voices: Dictionary mapping character names to descriptions
            session_folder: Optional path to the session folder
            
        Returns:
            True if successful, False otherwise
        """
        if session_folder:
            # If session folder is provided, save there
            filepath = os.path.join(session_folder, "character_voices.json")
        else:
            # Otherwise save to default location
            filepath = self.characters_path
            
        return save_json_to_file(character_voices, filepath)
    
    def save_scene_summaries(self, scene_summaries: Dict[str, List[Dict[str, Any]]], 
                            session_folder: str) -> bool:
        """
        Save scene summaries to JSON.
        
        Args:
            scene_summaries: Dictionary with scene information
            session_folder: Path to the session folder
            
        Returns:
            True if successful, False otherwise
        """
        filepath = os.path.join(session_folder, "scene_summaries.json")
        return save_json_to_file(scene_summaries, filepath)
    
    def load_character_voices(self) -> Dict[str, str]:
        """
        Load character voice descriptions.
        
        Returns:
            Dictionary mapping character names to voice descriptions
        """
        data = load_json_from_file(self.characters_path)
        return data if data else {}
    
    def expand_story(self, project_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Expand a story structure into detailed scene descriptions.
        
        Args:
            project_id: Optional project ID to use project data directly
            
        Returns:
            Tuple of (success, error_message or output_path)
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False, "Playwright modules not available"
        
        try:
            self._log("Starting story expansion...")
            
            # If project_id is provided, get project data
            if project_id:
                from modules.ui.playwright.project_manager import ProjectManager
                project_manager = ProjectManager(logger=self.logger)
                project_data = project_manager.get_project_data(project_id)
                
                if not project_data:
                    return False, f"Project not found: {project_id}"
                    
                # Create output path in project folder
                session_dir = os.path.join("data/play_projects", project_id, "generation_sessions", f"session_{int(time.time())}")
                os.makedirs(session_dir, exist_ok=True)
                expanded_output = os.path.join(session_dir, "expanded_story.json")
                    
                # Create StoryExpander with default paths
                expander = StoryExpander()
                
                # Call with direct data
                result_path = expander.expand_all_scenes(
                    output_path=expanded_output,
                    scene_summaries_data={"scenes": project_data.get("scenes", [])},
                    character_voices_data=project_data.get("character_voices", {})
                )
                
            else:
                # Original implementation using file paths
                summaries_path = "data/prompts/scene_summaries.json"
                voices_path = self.characters_path
                expanded_output = self.expanded_story_path
                
                # Create StoryExpander with the specific paths
                expander = StoryExpander(
                    scene_summaries_path=summaries_path,
                    character_voices_path=voices_path
                )
                
                # Expand the story
                result_path = expander.expand_all_scenes(output_path=expanded_output)
            
            # Log the result
            self._log(f"Expanded story saved to {result_path}")
            
            return True, result_path
            
        except Exception as e:
            error_msg = f"Error expanding story: {str(e)}"
            self._log(error_msg, "error")
            return False, error_msg

    def _create_symlinks(self, session_folder: str) -> None:
        """
        Create symlinks (or copies) for StoryExpander to find files.
        
        Args:
            session_folder: Path to the session folder
        """
        try:
            import shutil
            
            # Define target paths that StoryExpander expects
            target_scene_summaries = "data/prompts/scene_summaries.json"
            target_character_voices = "data/prompts/character_voices.json"
            
            # Source paths in the session folder
            source_scene_summaries = os.path.join(session_folder, "scene_summaries.json")
            source_character_voices = os.path.join(session_folder, "character_voices.json")
            
            # Ensure target directory exists
            ensure_directory(os.path.dirname(target_scene_summaries))
            
            # Remove existing files if they exist
            for path in [target_scene_summaries, target_character_voices]:
                if os.path.exists(path):
                    os.remove(path)
            
            # Create physical copies
            shutil.copy2(source_scene_summaries, target_scene_summaries)
            shutil.copy2(source_character_voices, target_character_voices)
            
            self._log("Created file copies from session folder to target paths")
        except Exception as e:
            self._log(f"Error creating symlinks: {e}", "error")