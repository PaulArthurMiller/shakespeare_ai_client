"""
UI Playwright Adapter for Shakespeare AI.

This module provides a facade interface between the Streamlit UI and the
underlying playwright functionality, delegating to specialized handlers
for different aspects of the playwriting process.
"""
import os
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

# Import handlers
from modules.ui.playwright.project_manager import ProjectManager
from modules.ui.playwright.scene_generator import SceneGenerator
from modules.ui.playwright.story_manager import StoryManager
from modules.ui.playwright.export_manager import ExportManager
from modules.ui.playwright.config_manager import PlaywrightConfigManager

# Import utils
from modules.ui.file_helper import ensure_directory
from modules.utils.logger import CustomLogger

# Check if core playwright modules are available
try:
    from modules.playwright.story_expander import StoryExpander
    from modules.playwright.scene_writer import SceneWriter
    from modules.playwright.artistic_adjuster import ArtisticAdjuster
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    print("Warning: Playwright modules not available")
    PLAYWRIGHT_AVAILABLE = False


class UIPlaywright:
    """
    Facade class for interfacing between the UI and the playwright functionality.
    Delegates to specialized handlers for different aspects of the playwriting process.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the UI playwright facade.
        
        Args:
            logger: Optional logger object (for Streamlit)
        """
        self.logger = logger
        self._log("Initializing UIPlaywright")
        
        # Base paths
        self.base_output_dir = "data/modern_play"
        
        # Initialize specialized handlers
        self.project_manager = ProjectManager(logger=self.logger)
        self.scene_generator = SceneGenerator(logger=self.logger)
        self.story_manager = StoryManager(logger=self.logger)
        self.export_manager = ExportManager(logger=self.logger)
        self.config_manager = PlaywrightConfigManager(logger=self.logger)
        
        # Create necessary directories
        ensure_directory(self.base_output_dir)
        ensure_directory("data/play_projects")
        
        # Log initialization status
        if not PLAYWRIGHT_AVAILABLE:
            self._log("Warning: Playwright modules not available. Limited functionality.")
    
    def _log(self, message: str, level: str = "info") -> None:
        """
        Log a message using the appropriate logger.
        
        Args:
            message: Message to log
            level: Log level (info, error, warning, debug, critical)
        """
        if self.logger:
            if hasattr(self.logger, "_log"):
                self.logger._log(message, level)
            elif hasattr(self.logger, level):
                getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    # Configuration management methods
    def update_playwright_config(self, config: Dict[str, Any]) -> bool:
        """
        Update the playwright configuration.
        
        Args:
            config: Dictionary with configuration settings
                
        Returns:
            True if successful, False otherwise
        """
        return self.config_manager.update_config(config)
    
    # Project management methods
    def manage_project_creation(self, title: str, thematic_guidelines: str, 
                             character_voices: Dict[str, str]) -> str:
        """
        Create a new play project with persistent metadata.
        
        Args:
            title: Title of the play
            thematic_guidelines: Overall thematic guidance for the play
            character_voices: Dictionary mapping character names to voice descriptions
            
        Returns:
            project_id: Unique identifier for the project
        """
        return self.project_manager.create_project(
            title=title, 
            thematic_guidelines=thematic_guidelines,
            character_voices=character_voices
        )
    
    def manage_scene_addition(self, project_id: str, act: str, scene: str, 
                           overview: str, setting: str, 
                           characters: List[str],
                           additional_instructions: str = "") -> bool:
        """
        Add a scene definition to a project without generating it.
        
        Args:
            project_id: Project identifier
            act: Act identifier
            scene: Scene identifier
            overview: Scene summary/description
            setting: Scene setting description
            characters: List of character names present in scene
            additional_instructions: Optional additional notes
            
        Returns:
            Success flag
        """
        return self.project_manager.add_scene(
            project_id=project_id,
            act=act,
            scene=scene,
            overview=overview,
            setting=setting,
            characters=characters,
            additional_instructions=additional_instructions
        )
    
    def get_project_list(self) -> List[Dict[str, Any]]:
        """
        Get a list of all available projects.
        
        Returns:
            List of project metadata dictionaries
        """
        return self.project_manager.list_projects()
    
    def get_project_details(self, project_id: str) -> Dict[str, Any]:
        """
        Get project data for a specific project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project data dictionary
        """
        return self.project_manager.get_project_data(project_id)
    
    # Scene generation methods
    def generate_single_scene(self, project_id: str, act: str, scene: str,
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
        return self.scene_generator.generate_project_scene(
            project_id=project_id,
            act=act,
            scene=scene,
            length_option=length_option
        )
    
    def generate_complete_project(self, project_id: str, 
                               length_option: str = "medium") -> Tuple[bool, str]:
        """
        Generate all scenes for a project and combine them into a full play.
        
        Args:
            project_id: Project identifier
            length_option: Scene length option ("short", "medium", "long")
            
        Returns:
            Tuple of (success, output_path or error_message)
        """
        return self.scene_generator.generate_full_project(
            project_id=project_id,
            length_option=length_option
        )
    
    def generate_all_scenes(self, length_option: str = "medium") -> Tuple[bool, str]:
        """
        Generate scenes from the expanded story.
        
        Args:
            length_option: Scene length option ("short", "medium", "long")
            
        Returns:
            Tuple of (success, error_message or output_directory)
        """
        return self.scene_generator.generate_scenes(length_option=length_option)
    
    # Note: Scene adjustment functionality is experimental and not currently 
    # connected to the UI. This can be activated for future development if needed.
    def generate_scene_adjustment(self, scene_path: str, critique: str, 
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
        return self.scene_generator.adjust_scene(
            scene_path=scene_path,
            critique=critique,
            output_dir=output_dir or os.path.join(self.base_output_dir, "final_edits")
        )
    
    # Story expansion methods
    def expand_story_details(self) -> Tuple[bool, str]:
        """
        Expand a story structure into detailed scene descriptions.
        
        Returns:
            Tuple of (success, error_message or output_path)
        """
        return self.story_manager.expand_story()
    
    # Export methods
    def export_scene_file(self, project_id: str, act: str, scene: str, 
                       output_format: str = "docx") -> Tuple[bool, str]:
        """
        Save a specific scene to a file in the desired format.
        
        Args:
            project_id: Project identifier
            act: Act identifier
            scene: Scene identifier
            output_format: Output format ("docx" or "md")
            
        Returns:
            Tuple of (success, output_path)
        """
        return self.export_manager.save_scene_to_file(
            project_id=project_id,
            act=act,
            scene=scene,
            output_format=output_format
        )
    
    def export_full_play_file(self, project_id: str, 
                           output_format: str = "docx") -> Tuple[bool, str]:
        """
        Save all scenes as a full play file in the desired format.
        
        Args:
            project_id: Project identifier
            output_format: Output format ("docx" or "md")
            
        Returns:
            Tuple of (success, output_path)
        """
        return self.export_manager.save_full_play_to_file(
            project_id=project_id,
            output_format=output_format
        )
    
    def export_combined_scenes(self, output_filename: Optional[str] = None) -> Tuple[bool, str]:
        """
        Combine all generated scenes into a single play file.
        
        Args:
            output_filename: Optional output filename
            
        Returns:
            Tuple of (success, error_message or output_path)
        """
        return self.export_manager.combine_scenes(
            base_output_dir=self.base_output_dir,
            output_filename=output_filename
        )


# Create a function to get a singleton instance
_INSTANCE = None

def get_ui_playwright(logger=None) -> UIPlaywright:
    """
    Get the UIPlaywright instance (singleton pattern).
    
    Args:
        logger: Optional logger object
        
    Returns:
        UIPlaywright instance
    """
    global _INSTANCE
    
    if _INSTANCE is None:
        _INSTANCE = UIPlaywright(logger=logger)
    elif logger is not None:
        # Simply replace the logger, no logging about the switch
        _INSTANCE.logger = logger
    
    return _INSTANCE