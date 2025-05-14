"""
Scene Generator for Shakespeare AI.

This module handles scene generation from expanded story structures,
as well as adjusting scenes based on critiques.
"""
import os
import shutil
import time
from typing import Dict, List, Any, Optional, Tuple

from modules.ui.file_helper import (
    load_text_from_file,
    save_text_to_file,
    ensure_directory,
    extract_act_scene_from_filename
)

# Check if core playwright modules are available
try:
    from modules.playwright.scene_writer import SceneWriter
    from modules.playwright.story_expander import StoryExpander
    from modules.playwright.artistic_adjuster import ArtisticAdjuster
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class SceneGenerator:
    """
    Handles scene generation operations for the Shakespeare AI playwright.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the scene generator.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger
        self.base_output_dir = "data/modern_play"
        self.expanded_story_path = os.path.join(self.base_output_dir, "expanded_story.json")
        
        # Ensure directories exist
        ensure_directory(self.base_output_dir)
        ensure_directory(os.path.join(self.base_output_dir, "generated_scenes"))
    
    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the provided logger if available."""
        if self.logger:
            if hasattr(self.logger, "_log"):
                self.logger._log(message, level)
            elif hasattr(self.logger, level):
                getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def generate_scenes(self, length_option: str = "medium") -> Tuple[bool, str]:
        """
        Generate scenes from the expanded story.
        
        Args:
            length_option: Scene length option ("short", "medium", or "long")
            
        Returns:
            Tuple of (success, error_message or output_directory)
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False, "Playwright modules not available"
        
        try:
            self._log("Starting scene generation...")
            
            # Ensure the expanded story exists
            if not os.path.exists(self.expanded_story_path):
                return False, f"Expanded story not found at {self.expanded_story_path}"
            
            # Create SceneWriter with the length option
            writer = SceneWriter(
                config_path="modules/playwright/config.py",
                expanded_story_path=self.expanded_story_path,
                length_option=length_option
            )
            
            # Generate scenes
            writer.generate_scenes()
            
            # Log the result
            self._log(f"Scenes saved to {writer.output_dir}")
            
            return True, writer.output_dir
        except Exception as e:
            error_msg = f"Error generating scenes: {str(e)}"
            self._log(error_msg, "error")
            return False, error_msg
    
    # Note: Scene adjustment functionality is experimental and not currently 
    # connected to the UI. This can be activated for future development if needed.
    def adjust_scene(self, scene_path: str, critique: str,
                    output_dir: Optional[str] = None) -> Tuple[bool, str]:
        """
        Adjust a scene based on a critique.
        
        Args:
            scene_path: Path to the scene file
            critique: Critique text
            output_dir: Optional output directory
            
        Returns:
            Tuple of (success, error_message or adjusted_text)
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False, "Playwright modules not available"
        
        try:
            self._log(f"Adjusting scene: {scene_path}")
            
            # Ensure the scene file exists
            if not os.path.exists(scene_path):
                return False, f"Scene file not found at {scene_path}"
            
            # Determine output directory
            if output_dir is None:
                output_dir = os.path.join(self.base_output_dir, "final_edits")
            
            ensure_directory(output_dir)
            
            # Create ArtisticAdjuster
            adjuster = ArtisticAdjuster()
            
            # Adjust the scene
            adjusted_text = adjuster.revise_scene(
                scene_path=scene_path,
                critique=critique,
                output_dir=output_dir
            )
            
            # Log the result
            self._log(f"Scene adjustment completed")
            
            return True, adjusted_text
        except Exception as e:
            error_msg = f"Error adjusting scene: {str(e)}"
            self._log(error_msg, "error")
            return False, error_msg
    
    def generate_project_scene(self, project_id: str, act: str, scene: str,
                            length_option: str = "medium") -> Tuple[bool, str, str]:
        """
        Generate a specific scene from a project.
        
        Args:
            project_id: Project identifier
            act: Act identifier
            scene: Scene identifier
            length_option: Scene length option ("short", "medium", "long")
            
        Returns:
            Tuple of (success, scene_content or error_message, scene_path)
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False, "Playwright modules not available", ""
        
        try:
            self._log(f"Generating scene for project {project_id}: Act {act}, Scene {scene}")
            
            # Get project data
            from modules.ui.playwright.project_manager import ProjectManager
            project_manager = ProjectManager(logger=self.logger)
            project_data = project_manager.get_project_data(project_id)
            
            if not project_data:
                return False, f"Project not found: {project_id}", ""
                
            # Find the scene data
            scene_data = None
            for s in project_data.get("scenes", []):
                if s.get("act") == act and s.get("scene") == scene:
                    scene_data = s
                    break
            
            if not scene_data:
                return False, f"Scene {act}.{scene} not found in project", ""
            
            # Create a session folder for this generation with a timestamp
            project_folder = os.path.join("data/play_projects", project_id)
            session_timestamp = time.strftime('%Y%m%d_%H%M%S')
            session_folder = os.path.join(project_folder, "generation_sessions", f"session_{session_timestamp}")
            ensure_directory(session_folder)
            
            # Project-specific expanded story path and scenes output directory
            expanded_story_path = os.path.join(session_folder, "expanded_story.json")
            scenes_output_dir = os.path.join(project_folder, "scenes")
            ensure_directory(scenes_output_dir)
            
            # Create scene summaries for StoryExpander
            scene_summary = {
                "act": act,
                "scene": scene,
                "overview": scene_data.get("overview", ""),
                "setting": scene_data.get("setting", ""),
                "characters": scene_data.get("characters", []),
                "additional_instructions": scene_data.get("additional_instructions", "")
            }
            
            scene_summaries = {"scenes": [scene_summary]}
            
            # Use StoryManager to handle the scene expansion
            from modules.ui.playwright.story_manager import StoryManager
            story_manager = StoryManager(logger=self.logger)
            
            # Save necessary files for StoryExpander
            scene_summaries_path = os.path.join(session_folder, "scene_summaries.json")
            character_voices_path = os.path.join(session_folder, "character_voices.json")
            
            if not story_manager.save_scene_summaries(scene_summaries, session_folder):
                return False, "Failed to save scene summaries", ""
                
            if not story_manager.save_character_voices(
                project_data.get("character_voices", {}), session_folder):
                return False, "Failed to save character voices", ""
            
            # Run the story expander directly with project-specific paths
            try:
                self._log("Starting story expansion...")
                expander = StoryExpander(
                    config_path="modules/playwright/config.py",
                    scene_summaries_path=scene_summaries_path,
                    character_voices_path=character_voices_path,
                    output_path=expanded_story_path
                )
                
                # Expand the story and get the output path
                expanded_story_path = expander.expand_all_scenes()
                
                self._log(f"Expanded story saved to {expanded_story_path}")
            except Exception as e:
                error_msg = f"Error expanding story: {str(e)}"
                self._log(error_msg, "error")
                return False, error_msg, ""
            
            # Now run the scene writer with the project-specific paths
            try:
                self._log("Starting scene generation...")
                
                writer = SceneWriter(
                    config_path="modules/playwright/config.py",
                    expanded_story_path=expanded_story_path,
                    output_dir=scenes_output_dir,
                    length_option=length_option
                )
                
                # Generate scenes
                writer.generate_scenes()
                
                self._log(f"Scenes saved to {scenes_output_dir}")
            except Exception as e:
                error_msg = f"Error generating scenes: {str(e)}"
                self._log(error_msg, "error")
                return False, error_msg, ""
            
            # Get the generated scene file path
            scene_md_filename = f"act_{act.lower()}_scene_{scene.lower()}.md"
            scene_json_filename = f"act_{act.lower()}_scene_{scene.lower()}.json"
            scene_md_path = os.path.join(scenes_output_dir, scene_md_filename)
            
            if not os.path.exists(scene_md_path):
                return False, f"Generated scene file not found: {scene_md_path}", ""
            
            # Read the generated scene
            scene_content = load_text_from_file(scene_md_path)
            if not scene_content:
                return False, f"Failed to read generated scene file: {scene_md_path}", ""
            
            return True, scene_content, scene_md_path
            
        except Exception as e:
            error_msg = f"Error generating project scene: {str(e)}"
            self._log(error_msg, "error")
            return False, error_msg, ""
    
    def generate_full_project(self, project_id: str, 
                            length_option: str = "medium") -> Tuple[bool, str]:
        """
        Generate all scenes for a project and combine them into a full play.
        This is a simplified version that delegates to generate_project_scene
        for each scene, then combines the results.
        
        Args:
            project_id: Project identifier
            length_option: Scene length option
            
        Returns:
            Tuple of (success, output_path or error_message)
        """
        try:
            self._log(f"Generating all scenes for project {project_id}")
            
            # Get project data
            from modules.ui.playwright.project_manager import ProjectManager
            project_manager = ProjectManager(logger=self.logger)
            project_data = project_manager.get_project_data(project_id)
            
            if not project_data:
                return False, f"Project not found: {project_id}"
            
            # Project folder
            project_folder = os.path.join("data/play_projects", project_id)
            project_scenes_dir = os.path.join(project_folder, "scenes")
            ensure_directory(project_scenes_dir)
            
            # Generate each scene
            scenes = project_data.get("scenes", [])
            if not scenes:
                return False, "No scenes defined in project"
            
            for scene_data in scenes:
                act = scene_data.get("act")
                scene = scene_data.get("scene")
                
                self._log(f"Generating scene {act}.{scene} for project {project_id}")
                
                success, result, _ = self.generate_project_scene(
                    project_id=project_id,
                    act=act,
                    scene=scene,
                    length_option=length_option
                )
                
                if not success:
                    self._log(f"Failed to generate scene {act}.{scene}: {result}", "warning")
                    # Continue with next scene despite failure
            
            # Combine all scenes into a full play
            from modules.ui.playwright.export_manager import ExportManager
            export_manager = ExportManager(logger=self.logger)
            
            return export_manager.combine_scenes_in_project(
                project_id=project_id,
                output_filename=f"{project_data.get('title', 'play')}_full.md"
            )
            
        except Exception as e:
            error_msg = f"Error generating full project: {str(e)}"
            self._log(error_msg, "error")
            return False, error_msg