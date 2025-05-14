"""
File Helper for Shakespeare AI UI.

This module provides utility functions for file operations needed by the UI,
such as handling uploaded files, parsing scene files, and managing output directories.
"""
import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Set, Union
from pathlib import Path


def ensure_directory(directory: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Path to the directory
    """
    os.makedirs(directory, exist_ok=True)


def extract_act_scene_from_filename(filepath: str) -> Tuple[str, str]:
    """
    Extract act and scene numbers from a filename.
    
    Args:
        filepath: Path to the file
        
    Returns:
        Tuple of (act, scene) identifiers
    """
    filename = os.path.basename(filepath)
    
    # Try common format patterns
    patterns = [
        r"act_?(\w+)_?scene_?(\w+)",  # act_1_scene_2, act1_scene2, etc.
        r"a(\w+)s(\w+)",              # a1s2, aIs, etc.
        r"(\w+)_(\w+)",               # I_1, 1_2, etc.
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            # Clean any trailing underscores from matched groups
            act = match.group(1).rstrip('_')
            scene = match.group(2).rstrip('_')
            return act, scene
    
    # Default if no pattern matches
    return "unknown", "unknown"


def parse_markdown_scene(filepath: str) -> List[str]:
    """
    Parse a markdown file to extract individual dialogue lines for translation.
    Skip headers, blank lines, stage directions, and character names.
    
    Args:
        filepath: Path to the markdown file
        
    Returns:
        List of dialogue lines
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return []
    
    # Split into lines
    lines = content.split('\n')
    
    # Filter out headers, blank lines, and stage directions
    dialogue_lines = []
    for line in lines:
        line = line.strip()
        # Skip if empty or looks like a header, stage direction, or character name
        if (not line or 
            line.startswith('#') or 
            line.startswith('---') or
            (line.startswith('[') and line.endswith(']')) or
            line.isupper()):
            continue
        dialogue_lines.append(line)
    
    return dialogue_lines


def gather_scene_files(input_dir: str, file_pattern: str = "*.md") -> List[Tuple[str, str, str, str]]:
    """
    Gather and sort scene files from a directory.
    
    Args:
        input_dir: Directory containing scene files
        file_pattern: Glob pattern to match scene files
        
    Returns:
        List of tuples: (filepath, filename, act, scene)
    """
    scene_files = []
    
    # Get all files matching pattern
    file_paths = list(Path(input_dir).glob(file_pattern))
    
    for filepath in file_paths:
        filename = filepath.name
        act, scene = extract_act_scene_from_filename(str(filepath))
        
        if act == "unknown" or scene == "unknown":
            # Skip files we can't parse
            continue
        
        scene_files.append((str(filepath), filename, act, scene))
    
    # Sort by act and scene
    def sort_key(item):
        act, scene = item[2], item[3]
        
        # Try to convert act to number (handle roman numerals)
        try:
            if re.match(r'^[IVXLCDM]+$', act.upper()):
                act_num = roman_to_int(act.upper())
            else:
                act_num = float(act)
        except (ValueError, TypeError):
            act_num = act  # Keep as string if conversion fails
            
        # Try to convert scene to number
        try:
            if re.match(r'^[IVXLCDM]+$', scene.upper()):
                scene_num = roman_to_int(scene.upper())
            else:
                scene_num = float(scene)
        except (ValueError, TypeError):
            scene_num = scene  # Keep as string if conversion fails
            
        return (act_num, scene_num)
    
    return sorted(scene_files, key=sort_key)


def roman_to_int(roman: str) -> int:
    """
    Convert a Roman numeral to an integer.
    
    Args:
        roman: Roman numeral string
        
    Returns:
        Integer value
    """
    values = {
        'I': 1, 'V': 5, 'X': 10, 'L': 50, 
        'C': 100, 'D': 500, 'M': 1000
    }
    total = 0
    prev = 0
    
    for char in reversed(roman):
        if char not in values:
            return 0  # Invalid Roman numeral
        current = values[char]
        if current >= prev:
            total += current
        else:
            total -= current
        prev = current
        
    return total


def save_text_to_file(text: str, filepath: str) -> bool:
    """
    Save text content to a file.
    
    Args:
        text: Text content to save
        filepath: Path to the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        return True
    except Exception as e:
        print(f"Error saving file {filepath}: {e}")
        return False


def load_text_from_file(filepath: str) -> Optional[str]:
    """
    Load text content from a file.
    
    Args:
        filepath: Path to the file
        
    Returns:
        Text content or None if file not found
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None


def load_json_from_file(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Load JSON content from a file.
    
    Args:
        filepath: Path to the file
        
    Returns:
        Dictionary with JSON content or None if file not found
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {filepath}")
        return None
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None


def save_json_to_file(data: Dict[str, Any], filepath: str) -> bool:
    """
    Save JSON content to a file.
    
    Args:
        data: Dictionary to save as JSON
        filepath: Path to the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving file {filepath}: {e}")
        return False

def save_uploaded_file(uploaded_file: Any, target_dir: str, filename: Optional[str] = None) -> str:
    """
    Save an uploaded file from Streamlit.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        target_dir: Directory to save the file
        filename: Optional filename (uses original name if not provided)
        
    Returns:
        Path to the saved file
    """
    # Ensure directory exists
    ensure_directory(target_dir)
    
    # Use original filename if not provided
    if filename is None and hasattr(uploaded_file, 'name'):
        filename = uploaded_file.name
    
    # Ensure filename is a string
    if not isinstance(filename, str):
        # Provide a default filename if we can't get one
        filename = "uploaded_file.txt"
    
    # Full path
    filepath = os.path.join(target_dir, filename)
    
    try:
        # Save the file
        with open(filepath, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        return filepath
    except Exception as e:
        print(f"Error saving uploaded file {filename}: {e}")
        return ""


def load_translated_scene(json_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Load a translated scene from a JSON file.
    
    Args:
        json_path: Path to the JSON file
        
    Returns:
        Tuple of (translated_lines, original_lines)
    """
    scene_data = load_json_from_file(json_path)
    if not scene_data:
        return [], []
    
    translated_lines = scene_data.get("translated_lines", [])
    original_lines = scene_data.get("original_lines", [])
    
    # If original_lines is not available, try to extract from translated_lines
    if not original_lines and translated_lines:
        original_lines = []
        for line in translated_lines:
            if "original_modern_line" in line:
                original_lines.append(line["original_modern_line"])
    
    return translated_lines, original_lines


def get_translation_preview(json_path: str, max_lines: int = 5) -> str:
    """
    Generate a preview of a translated scene for display in the UI.
    
    Args:
        json_path: Path to the JSON file
        max_lines: Maximum number of lines to include in the preview
        
    Returns:
        Formatted string with scene preview
    """
    translated_lines, original_lines = load_translated_scene(json_path)
    
    if not translated_lines:
        return "No translation data available."
    
    # Limit the number of lines for preview
    translated_lines = translated_lines[:max_lines]
    if len(original_lines) < len(translated_lines):
        original_lines.extend([""] * (len(translated_lines) - len(original_lines)))
    else:
        original_lines = original_lines[:max_lines]
    
    # Format the preview
    preview_lines = []
    for i, (t_line, o_line) in enumerate(zip(translated_lines, original_lines)):
        shakespeare_text = t_line.get("text", "")
        modern_text = o_line or t_line.get("original_modern_line", "")
        
        preview_lines.append(f"Line {i+1}:")
        preview_lines.append(f"Shakespeare: {shakespeare_text}")
        preview_lines.append(f"Modern: {modern_text}")
        preview_lines.append("")  # Blank line for readability
    
    if len(translated_lines) < max_lines:
        preview_lines.append(f"Total lines: {len(translated_lines)}")
    else:
        total_count = load_line_count(json_path)
        preview_lines.append(f"Preview of {max_lines} lines (total: {total_count})")
    
    return "\n".join(preview_lines)


def load_line_count(json_path: str) -> int:
    """
    Get the total number of lines in a translated scene.
    
    Args:
        json_path: Path to the JSON file
        
    Returns:
        Number of translated lines
    """
    scene_data = load_json_from_file(json_path)
    if not scene_data:
        return 0
    
    return len(scene_data.get("translated_lines", []))


def combine_scene_files(scene_files: List[Tuple[str, str, str, str]], output_path: str) -> bool:
    """
    Combine multiple scene files into a single play file.
    
    Args:
        scene_files: List of tuples (filepath, filename, act, scene)
        output_path: Path to save the combined play
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        directory = os.path.dirname(output_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        
        # Combine the files
        combined_text = ""
        for filepath, _, act, scene in scene_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                # Add act and scene headers if not already present
                if not content.startswith(f"# ACT {act.upper()}"):
                    combined_text += f"# ACT {act.upper()}\n\n"
                
                if not content.startswith(f"## SCENE {scene.upper()}") and not "## SCENE" in content[:100]:
                    combined_text += f"## SCENE {scene.upper()}\n\n"
                
                combined_text += content + "\n\n"
            except Exception as e:
                print(f"Error reading file {filepath}: {e}")
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(combined_text)
        
        return True
    except Exception as e:
        print(f"Error combining scene files: {e}")
        return False


def count_directory_files(directory: str, pattern: str = "*") -> int:
    """
    Count the number of files in a directory matching a pattern.
    
    Args:
        directory: Directory to search
        pattern: Glob pattern to match
        
    Returns:
        Number of matching files
    """
    if not os.path.exists(directory):
        return 0
    
    return len(list(Path(directory).glob(pattern)))


def get_output_file_summary(directory: str) -> Dict[str, int]:
    """
    Get a summary of output files in a directory.
    
    Args:
        directory: Directory to search
        
    Returns:
        Dictionary with counts of different file types
    """
    if not os.path.exists(directory):
        return {"json": 0, "markdown": 0, "other": 0, "total": 0}
    
    # Count files by extension
    json_count = count_directory_files(directory, "*.json")
    md_count = count_directory_files(directory, "*.md")
    total_count = count_directory_files(directory)
    other_count = total_count - json_count - md_count
    
    return {
        "json": json_count,
        "markdown": md_count,
        "other": other_count,
        "total": total_count
    }


def check_file_exists(filepath: str) -> bool:
    """
    Check if a file exists.
    
    Args:
        filepath: Path to the file
        
    Returns:
        True if the file exists, False otherwise
    """
    return os.path.exists(filepath) and os.path.isfile(filepath)


def extract_lines_from_streamlit_input(text_input: str) -> List[str]:
    """
    Extract lines from a multi-line text input in Streamlit.
    
    Args:
        text_input: Multi-line text from a Streamlit text area
        
    Returns:
        List of non-empty lines
    """
    if not text_input:
        return []
    
    # Split by newline and remove empty lines
    lines = [line.strip() for line in text_input.split('\n')]
    return [line for line in lines if line]


def list_recent_translations(limit: int = 5) -> List[Dict[str, Any]]:
    """
    List recent translations from all sessions.
    
    Args:
        limit: Maximum number of translations to return
        
    Returns:
        List of dictionaries with translation information
    """
    from modules.ui.session_manager import get_all_sessions
    
    sessions = get_all_sessions()
    recent_translations = []
    
    for session in sessions:
        for scene in session.get("scenes_translated", []):
            scene_info = {
                "translation_id": session.get("translation_id", "unknown"),
                "act": scene.get("act", "unknown"),
                "scene": scene.get("scene", "unknown"),
                "translated_at": scene.get("translated_at", "unknown"),
                "line_count": scene.get("line_count", 0),
                "output_dir": session.get("output_dir", "")
            }
            recent_translations.append(scene_info)
    
    # Sort by translated_at, newest first
    recent_translations.sort(
        key=lambda x: x.get("translated_at", ""),
        reverse=True
    )
    
    return recent_translations[:limit]