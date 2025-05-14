"""
Project Manager for Shakespeare AI.

This module handles project-related operations, including creation,
loading, and managing project metadata.
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from modules.ui.file_helper import (
    load_json_from_file,
    save_json_to_file,
    ensure_directory
)


class ProjectManager:
    """
    Handles project management operations for the Shakespeare AI playwright.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the project manager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger
        self.projects_dir = "data/play_projects"
        ensure_directory(self.projects_dir)
    
    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the provided logger if available."""
        if self.logger:
            if hasattr(self.logger, "_log"):
                self.logger._log(message, level)
            elif hasattr(self.logger, level):
                getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def create_project(self, title: str, thematic_guidelines: str, 
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
        # Generate unique project ID
        project_id = f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_folder = os.path.join(self.projects_dir, project_id)
        ensure_directory(project_folder)
        ensure_directory(os.path.join(project_folder, "scenes"))
        
        # Create initial project data
        project_data = {
            "title": title,
            "thematic_guidelines": thematic_guidelines,
            "character_voices": character_voices,
            "scenes": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Save project data
        self._save_project_data(project_id, project_data)
        
        self._log(f"Created new play project: {title} (ID: {project_id})")
        return project_id
    
    def add_scene(self, project_id: str, act: str, scene: str, 
                 overview: str, setting: str, characters: List[str],
                 additional_instructions: str = "") -> bool:
        """
        Add a scene definition to a project without generating it.
        
        Args:
            project_id: Project identifier
            act: Act identifier (e.g., "I", "II")
            scene: Scene identifier (e.g., "1", "2")
            overview: Scene summary/description
            setting: Scene setting description
            characters: List of character names present in scene
            additional_instructions: Optional additional notes
            
        Returns:
            Success flag
        """
        # Get project data
        project_data = self.get_project_data(project_id)
        if not project_data:
            self._log(f"Project not found: {project_id}", "error")
            return False
        
        # Create scene summary
        scene_data = {
            "act": act,
            "scene": scene,
            "overview": overview,
            "setting": setting,
            "characters": characters,
            "additional_instructions": additional_instructions
        }
        
        # Add or update scene in project
        scenes = project_data.get("scenes", [])
        
        # Check if scene already exists
        for i, s in enumerate(scenes):
            if s.get("act") == act and s.get("scene") == scene:
                # Update existing scene
                scenes[i] = scene_data
                break
        else:
            # Add new scene
            scenes.append(scene_data)
        
        # Update scenes list
        project_data["scenes"] = scenes
        
        # Save updated project data
        success = self._save_project_data(project_id, project_data)
        
        if success:
            self._log(f"Added scene {act}.{scene} to project {project_id}")
        
        return success
    
    def _save_project_data(self, project_id: str, project_data: Dict[str, Any]) -> bool:
        """
        Save project data to the project file.
        
        Args:
            project_id: Project identifier
            project_data: Project data dictionary
            
        Returns:
            Success flag
        """
        project_folder = os.path.join(self.projects_dir, project_id)
        project_file = os.path.join(project_folder, "project.json")
        
        # Update the timestamp
        project_data["updated_at"] = datetime.now().isoformat()
        
        return save_json_to_file(project_data, project_file)
    
    def get_project_data(self, project_id: str) -> Dict[str, Any]:
        """
        Get project data for a specific project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project data dictionary or empty dict if not found
        """
        project_file = os.path.join(self.projects_dir, project_id, "project.json")
        data = load_json_from_file(project_file)
        return data if data else {}
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        Get a list of all available projects.
        
        Returns:
            List of project metadata dictionaries
        """
        projects = []
        
        if not os.path.exists(self.projects_dir):
            return []
        
        for item in os.listdir(self.projects_dir):
            project_folder = os.path.join(self.projects_dir, item)
            if os.path.isdir(project_folder):
                project_file = os.path.join(project_folder, "project.json")
                if os.path.exists(project_file):
                    try:
                        project_data = load_json_from_file(project_file)
                        if project_data:
                            # Create a summary
                            projects.append({
                                "id": item,
                                "title": project_data.get("title", "Untitled"),
                                "scenes": len(project_data.get("scenes", [])),
                                "characters": len(project_data.get("character_voices", {})),
                                "created_at": project_data.get("created_at", ""),
                                "updated_at": project_data.get("updated_at", "")
                            })
                    except Exception as e:
                        self._log(f"Error loading project {item}: {e}", "error")
        
        # Sort by updated_at, newest first
        projects.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        
        return projects
    
    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Success flag
        """
        project_folder = os.path.join(self.projects_dir, project_id)
        if not os.path.exists(project_folder):
            self._log(f"Project not found: {project_id}", "error")
            return False
        
        try:
            import shutil
            shutil.rmtree(project_folder)
            self._log(f"Deleted project: {project_id}")
            return True
        except Exception as e:
            self._log(f"Error deleting project {project_id}: {e}", "error")
            return False