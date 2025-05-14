"""
Translation Session Manager for Shakespeare AI.

This module handles the creation, retrieval, and management of translation sessions,
providing an interface between the UI and the underlying translation system.
"""
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path

# Constants
TRANSLATION_SESSIONS_DIR = "translation_sessions"
TRANSLATION_INFO_FILE = "translation_info.json"


def setup_session_directory() -> None:
    """Ensure the translation sessions directory exists."""
    os.makedirs(TRANSLATION_SESSIONS_DIR, exist_ok=True)


def generate_translation_id() -> str:
    """
    Generate a user-friendly translation ID with timestamp and a short random part.
    
    Returns:
        A unique translation ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    random_part = str(uuid.uuid4())[:6]  # Just take 6 characters from the UUID
    return f"trans_{timestamp}_{random_part}"


def get_session_info_path(translation_id: str) -> str:
    """
    Get the path to the information file for a specific translation session.
    
    Args:
        translation_id: The translation session ID
        
    Returns:
        Path to the session information file
    """
    return os.path.join(TRANSLATION_SESSIONS_DIR, f"{translation_id}_{TRANSLATION_INFO_FILE}")


def get_session_info(translation_id: str) -> Dict[str, Any]:
    """
    Get information about a specific translation session.
    
    Args:
        translation_id: The translation session ID
        
    Returns:
        Dictionary with session information or empty dict if not found
    """
    setup_session_directory()
    info_path = get_session_info_path(translation_id)
    
    if os.path.exists(info_path):
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading session info for {translation_id}: {e}")
            # Return a minimal valid structure
            return {
                "translation_id": translation_id,
                "scenes_translated": [],
                "created_at": "unknown",
                "last_updated": "unknown",
                "output_dir": ""
            }
    else:
        # Return default/empty info
        return {
            "translation_id": translation_id,
            "scenes_translated": [],
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "output_dir": ""
        }


def get_all_sessions() -> List[Dict[str, Any]]:
    """
    Get information about all available translation sessions.
    
    Returns:
        List of dictionaries with session information, sorted by date (newest first)
    """
    setup_session_directory()
    
    # Find all session info files
    pattern = f"*_{TRANSLATION_INFO_FILE}"
    info_files = list(Path(TRANSLATION_SESSIONS_DIR).glob(pattern))
    
    sessions = []
    for info_file in info_files:
        try:
            # Extract translation ID from filename
            filename = info_file.name
            translation_id = filename.replace(f"_{TRANSLATION_INFO_FILE}", "")
            
            # Load session info
            with open(info_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
                
            # Ensure we have the translation ID in the info
            if "translation_id" not in info:
                info["translation_id"] = translation_id
                
            sessions.append(info)
        except Exception as e:
            print(f"Error loading session info from {info_file}: {e}")
    
    # Sort by last_updated, newest first (with fallback to created_at)
    return sorted(
        sessions,
        key=lambda x: x.get("last_updated", x.get("created_at", "")),
        reverse=True
    )


def create_new_session(output_dir: Optional[str] = None) -> str:
    """
    Create a new translation session.
    
    Args:
        output_dir: Optional output directory for the translation results
        
    Returns:
        The newly created translation ID
    """
    translation_id = generate_translation_id()
    
    # Set up default output directory if not provided
    if not output_dir:
        output_dir = os.path.join("outputs/translated_scenes", translation_id)
    
    # Create the output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create initial session info
    session_info = {
        "translation_id": translation_id,
        "scenes_translated": [],
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "output_dir": output_dir
    }
    
    # Save the session info
    save_session_info(translation_id, session_info)
    
    return translation_id


def save_session_info(translation_id: str, info: Dict[str, Any]) -> bool:
    """
    Save information about a translation session.
    
    Args:
        translation_id: The translation session ID
        info: Dictionary with session information
        
    Returns:
        True if successful, False otherwise
    """
    setup_session_directory()
    info_path = get_session_info_path(translation_id)
    
    try:
        # Update last_updated timestamp
        info["last_updated"] = datetime.now().isoformat()
        
        # Save to file
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2)
        
        # Also save a copy in the output directory for easy reference
        output_dir = info.get("output_dir", "")
        if output_dir and os.path.exists(output_dir):
            output_info_path = os.path.join(output_dir, TRANSLATION_INFO_FILE)
            with open(output_info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2)
                
        return True
    except Exception as e:
        print(f"Error saving session info for {translation_id}: {e}")
        return False


def update_scene_info(
    translation_id: str, 
    act: str, 
    scene: str, 
    filename: str, 
    line_count: int
) -> bool:
    """
    Update information about a translated scene.
    
    Args:
        translation_id: The translation session ID
        act: Act identifier
        scene: Scene identifier
        filename: Original filename
        line_count: Number of lines translated
        
    Returns:
        True if successful, False otherwise
    """
    # Get current session info
    info = get_session_info(translation_id)
    
    # New scene info
    scene_info = {
        "act": act,
        "scene": scene,
        "filename": filename,
        "translated_at": datetime.now().isoformat(),
        "line_count": line_count
    }
    
    # Check if this scene already exists
    scenes = info.get("scenes_translated", [])
    scene_updated = False
    
    for i, s in enumerate(scenes):
        if s.get("act") == act and s.get("scene") == scene:
            # Update existing scene
            scenes[i] = scene_info
            scene_updated = True
            break
    
    if not scene_updated:
        # Add new scene
        scenes.append(scene_info)
    
    # Update the scenes list
    info["scenes_translated"] = scenes
    
    # Save the updated info
    return save_session_info(translation_id, info)


def is_scene_translated(translation_id: str, act: str, scene: str) -> bool:
    """
    Check if a scene has already been translated in this session.
    
    Args:
        translation_id: The translation session ID
        act: Act identifier
        scene: Scene identifier
        
    Returns:
        True if the scene has been translated, False otherwise
    """
    info = get_session_info(translation_id)
    
    for s in info.get("scenes_translated", []):
        if s.get("act") == act and s.get("scene") == scene:
            return True
    
    return False


def delete_session(translation_id: str) -> bool:
    """
    Delete a translation session.
    
    Args:
        translation_id: The translation session ID
        
    Returns:
        True if successful, False otherwise
    """
    setup_session_directory()
    info_path = get_session_info_path(translation_id)
    
    if os.path.exists(info_path):
        try:
            os.remove(info_path)
            return True
        except Exception as e:
            print(f"Error deleting session {translation_id}: {e}")
            return False
    
    return False


def get_scene_files(act: str, scene: str, translation_id: str) -> Dict[str, str]:
    """
    Get file paths for a specific translated scene.
    
    Args:
        act: Act identifier
        scene: Scene identifier
        translation_id: The translation session ID
        
    Returns:
        Dictionary with paths for json and markdown files
    """
    # Get session info
    info = get_session_info(translation_id)
    output_dir = info.get("output_dir", "")
    
    if not output_dir or not os.path.exists(output_dir):
        return {"json": "", "markdown": ""}
    
    # Create scene identifier
    scene_id = f"act_{act.lower()}_scene_{scene.lower()}"
    
    # Get file paths
    json_path = os.path.join(output_dir, f"{scene_id}.json")
    md_path = os.path.join(output_dir, f"{scene_id}.md")
    
    return {
        "json": json_path if os.path.exists(json_path) else "",
        "markdown": md_path if os.path.exists(md_path) else ""
    }