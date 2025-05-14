"""
UI Translator Adapter for Shakespeare AI.

This module provides an interface between the Streamlit UI and the 
underlying translator functionality, handling user input validation,
error handling, and format conversion for the UI.
"""
import os
import time
from typing import Dict, List, Any, Optional, Tuple, Union, cast

# Import module-specific helpers
from modules.ui.file_helper import (
    parse_markdown_scene,
    extract_act_scene_from_filename,
    save_uploaded_file,
    load_translated_scene,
    ensure_directory
)
from modules.ui.session_manager import (
    get_session_info,
    update_scene_info,
    is_scene_translated
)

# Import the core translator functionality
try:
    from modules.translator.translation_manager import TranslationManager
    from modules.translator.scene_saver import SceneSaver
    TRANSLATOR_AVAILABLE = True
except ImportError:
    print("Warning: Translator modules not available")
    TRANSLATOR_AVAILABLE = False


class UITranslator:
    """
    Adapter class for interfacing between the UI and the translator functionality.
    """
    
    def __init__(self, translation_id: Optional[str] = None, logger=None):
        """
        Initialize the UI translator.
        
        Args:
            translation_id: Optional translation session ID
            logger: Optional logger object (for Streamlit)
        """
        self.translation_id = translation_id
        self.logger = logger  # For Streamlit logging
        
        # Explicit typing to avoid None-type errors
        self.translation_manager: Optional[TranslationManager] = None
        
        # Flag to track if the translator is initialized
        self.is_initialized = False
        
        # Check if translator modules are available
        if not TRANSLATOR_AVAILABLE:
            self._log("Warning: Translator modules not available. Limited functionality.")
    
    def _log(self, message: str, level: str = "info") -> None:
        """
        Log a message using the appropriate logger.
        
        Args:
            message: Message to log
            level: Log level (info, error, warning, debug)
        """
        # Always print to console during debugging
        print(f"[UITranslator] [{level.upper()}] {message}")
        
        if self.logger:
            # Check if it's our custom logger
            if hasattr(self.logger, "_log"):
                self.logger._log(message, level)
            elif hasattr(self.logger, level):
                # For Streamlit or other loggers that have direct methods
                getattr(self.logger, level)(message)
            else:
                # Last resort: try the most common method
                if hasattr(self.logger, "info"):
                    self.logger.info(f"[{level.upper()}] {message}")
    
    def initialize(self, force_reinit: bool = False) -> bool:
        """
        Initialize the translator components.
        
        Args:
            force_reinit: Force reinitialization even if already initialized
            
        Returns:
            True if successful, False otherwise
        """
        if self.is_initialized and not force_reinit:
            self._log("Translator already initialized")
            return True
        
        if not TRANSLATOR_AVAILABLE:
            self._log("Error: Translator modules not available", "error")
            return False
        
        self._log(f"Initializing translator with translation_id: {self.translation_id}")
        
        try:
            # Initialize the translation manager
            self._log("Creating TranslationManager instance")
            self.translation_manager = TranslationManager()
            
            # Start a translation session if we have an ID
            if self.translation_id:
                if self.translation_manager is not None:
                    self._log(f"Starting translation session with ID: {self.translation_id}")
                    self.translation_manager.start_translation_session(self.translation_id)
                    self._log("Translation session started successfully")
                else:
                    self._log("Failed to initialize translation manager", "error")
                    return False
            else:
                self._log("No translation ID provided, session not started", "warning")
            
            self.is_initialized = True
            self._log(f"Translator successfully initialized with ID: {self.translation_id}")
            return True
        except Exception as e:
            self._log(f"Error initializing translator: {e}", "error")
            # Print stack trace for debugging
            import traceback
            self._log(f"Stack trace: {traceback.format_exc()}", "error")
            return False
    
    def set_translation_id(self, translation_id: str) -> bool:
        """
        Set the translation ID and initialize the translator.
        
        Args:
            translation_id: Translation session ID
            
        Returns:
            True if successful, False otherwise
        """
        if not translation_id:
            self._log("Error: Empty translation ID provided")
            return False
            
        self.translation_id = translation_id
        
        # Re-initialize with the new ID
        return self.initialize(force_reinit=True)
    
    def translate_line(self, modern_line: str, use_hybrid_search: bool = True) -> Optional[Dict[str, Any]]:
        """
        Translate a single modern line to Shakespearean English.
        
        Args:
            modern_line: Modern English line
            use_hybrid_search: Whether to use hybrid search
            
        Returns:
            Dictionary with translation results or None if failed
        """
        if not self.is_initialized:
            if not self.initialize():
                return None
        
        if not modern_line or not modern_line.strip():
            self._log("Error: Empty line provided for translation")
            return None
            
        if self.translation_manager is None:
            self._log("Error: Translation manager not initialized")
            return None
            
        try:
            # Start a timer to measure translation time
            start_time = time.time()
            
            self._log(f"Translating line: '{modern_line}'")
            
            # Call the translation manager
            result = self.translation_manager.translate_line(
                modern_line=modern_line,
                selector_results={},  # Empty dict tells the translator to run its own search
                use_hybrid_search=use_hybrid_search
            )
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            
            if result:
                self._log(f"Translation completed in {elapsed_time:.2f} seconds")
                return result
            else:
                self._log(f"Translation failed after {elapsed_time:.2f} seconds")
                return None
                
        except Exception as e:
            self._log(f"Error translating line: {e}")
            return None
    
    def translate_lines(self, modern_lines: List[str], use_hybrid_search: bool = True) -> List[Dict[str, Any]]:
        """
        Translate multiple modern lines to Shakespearean English.
        
        Args:
            modern_lines: List of modern English lines
            use_hybrid_search: Whether to use hybrid search
            
        Returns:
            List of dictionaries with translation results
        """
        if not self.is_initialized:
            self._log("Translation manager not initialized. Attempting to initialize...", "warning")
            if not self.initialize():
                self._log("Failed to initialize translation manager", "error")
                return []
        
        if not modern_lines:
            self._log("Error: Empty list of lines provided for translation", "error")
            return []
            
        if self.translation_manager is None:
            self._log("Error: Translation manager is None", "error")
            return []
        
        try:
            # Log count of lines before and after filtering
            original_count = len(modern_lines)
            self._log(f"Translating {original_count} lines")
            
            # Filter out empty lines
            filtered_lines = [line for line in modern_lines if line and line.strip()]
            filtered_count = len(filtered_lines)
            
            if filtered_count < original_count:
                self._log(f"Filtered out {original_count - filtered_count} empty lines")
            
            if not filtered_lines:
                self._log("Error: All lines were empty after filtering", "error")
                return []
            
            # Sample some lines for debugging
            if filtered_lines:
                sample_size = min(3, len(filtered_lines))
                self._log(f"Sample of first {sample_size} lines to translate:")
                for i in range(sample_size):
                    self._log(f"  Line {i+1}: {filtered_lines[i][:50]}...")
                    
            # Call the translation manager
            self._log(f"Calling translation_manager.translate_group with {len(filtered_lines)} lines")
            start_time = time.time()
            
            results = self.translation_manager.translate_group(
                modern_lines=filtered_lines,
                use_hybrid_search=use_hybrid_search
            )
            
            elapsed_time = time.time() - start_time
            self._log(f"Translation completed for {len(results)}/{len(filtered_lines)} lines in {elapsed_time:.2f} seconds")
            
            # Log summary of results
            if len(results) < len(filtered_lines):
                self._log(f"Warning: {len(filtered_lines) - len(results)} lines failed to translate", "warning")
            
            return results
        except Exception as e:
            self._log(f"Error translating lines: {e}", "error")
            # Print stack trace for debugging
            import traceback
            self._log(f"Stack trace: {traceback.format_exc()}", "error")
            return []
    
    def translate_file(
        self, 
        filepath: str, 
        output_dir: Optional[str] = None,
        force_retranslate: bool = False,
        use_hybrid_search: bool = True
    ) -> Tuple[bool, str, int]:
        """
        Translate a file containing modern English lines.
        
        Args:
            filepath: Path to the file
            output_dir: Optional output directory (uses default if not provided)
            force_retranslate: Force retranslation even if already translated
            use_hybrid_search: Whether to use hybrid search
            
        Returns:
            Tuple of (success, output_path, lines_translated)
        """
        # Enable more detailed logging for debugging
        debug_mode = True
        
        if not self.is_initialized:
            self._log("Translation manager not initialized. Attempting to initialize...", "warning")
            if not self.initialize():
                self._log("Failed to initialize translation manager", "error")
                return False, "", 0
                
        if not self.translation_id:
            self._log("Error: No translation ID set for file translation", "error")
            return False, "", 0
            
        if not os.path.exists(filepath):
            self._log(f"Error: File not found: {filepath}", "error")
            return False, "", 0
        
        try:
            # Extract act and scene from filename
            act, scene = extract_act_scene_from_filename(filepath)
            self._log(f"Translating file: {filepath} (Act {act}, Scene {scene})")
            
            # Check if this scene has already been translated
            if not force_retranslate and is_scene_translated(self.translation_id, act, scene):
                self._log(f"Scene Act {act}, Scene {scene} has already been translated")
                
                # Get the output directory from session info
                session_info = get_session_info(self.translation_id)
                existing_output_dir = session_info.get("output_dir", "")
                
                if existing_output_dir and os.path.exists(existing_output_dir):
                    scene_id = f"act_{act.lower()}_scene_{scene.lower()}"
                    json_path = os.path.join(existing_output_dir, f"{scene_id}.json")
                    
                    if os.path.exists(json_path):
                        self._log(f"Loading existing translation from: {json_path}")
                        translated_lines, _ = load_translated_scene(json_path)
                        self._log(f"Found {len(translated_lines)} existing translated lines")
                        return True, existing_output_dir, len(translated_lines)
                
                self._log("No existing translation file found despite scene being marked as translated", "warning")
                return True, "", 0
            
            # Log file size for debugging
            file_size = os.path.getsize(filepath)
            self._log(f"File size: {file_size} bytes")
            
            # Parse the file to get dialogue lines
            self._log("Parsing markdown scene file to extract dialogue lines...")
            modern_lines = parse_markdown_scene(filepath)
            
            if not modern_lines:
                self._log("No dialogue lines found in file", "error")
                return False, "", 0
            
            self._log(f"Extracted {len(modern_lines)} dialogue lines from file")
            
            # Log a sample of the lines for debugging
            if debug_mode and modern_lines:
                sample_size = min(3, len(modern_lines))
                self._log(f"Sample of first {sample_size} lines:")
                for i in range(sample_size):
                    self._log(f"  Line {i+1}: {modern_lines[i][:50]}...")
            
            # Determine output directory
            actual_output_dir: str
            if output_dir is None:
                session_info = get_session_info(self.translation_id)
                actual_output_dir = session_info.get("output_dir", "outputs/translated_scenes")
                if not actual_output_dir:
                    actual_output_dir = "outputs/translated_scenes"
            else:
                actual_output_dir = output_dir
            
            self._log(f"Using output directory: {actual_output_dir}")
            
            # Now ensure_directory receives a string, not Optional[str]
            ensure_directory(actual_output_dir)
            self._log("Output directory confirmed to exist")
            
            # Translate the lines
            self._log(f"Starting translation of {len(modern_lines)} lines with hybrid_search={use_hybrid_search}")
            
            # Check if translation_manager is properly initialized
            if self.translation_manager is None:
                self._log("Error: translation_manager is None", "error")
                return False, "", 0
                
            # Add a progress indicator for long translations
            progress_report_interval = max(1, len(modern_lines) // 10)  # Report progress every ~10%
            
            translated_lines = []
            try:
                # Try using translate_group for batch processing
                self._log("Using batch translation with translate_group")
                translated_lines = self.translate_lines(
                    modern_lines=modern_lines,
                    use_hybrid_search=use_hybrid_search
                )
            except Exception as batch_error:
                self._log(f"Batch translation failed with error: {batch_error}", "error")
                self._log("Attempting line-by-line translation as fallback...", "warning")
                
                # Fallback to line-by-line translation
                translated_lines = []
                for i, line in enumerate(modern_lines):
                    try:
                        # Report progress periodically
                        if i % progress_report_interval == 0 or i == len(modern_lines) - 1:
                            self._log(f"Translating line {i+1}/{len(modern_lines)}")
                            
                        result = self.translate_line(line, use_hybrid_search=use_hybrid_search)
                        if result:
                            translated_lines.append(result)
                        else:
                            self._log(f"Failed to translate line {i+1}: {line[:50]}...", "warning")
                    except Exception as line_error:
                        self._log(f"Error translating line {i+1}: {line_error}", "error")
            
            # Check translation results
            if not translated_lines:
                self._log("Translation failed - no lines translated", "error")
                return False, "", 0
            
            self._log(f"Successfully translated {len(translated_lines)}/{len(modern_lines)} lines")
            
            # Save the translation using SceneSaver
            if TRANSLATOR_AVAILABLE:
                self._log("Initializing SceneSaver to save translation results")
                try:
                    saver = SceneSaver(translation_id=self.translation_id, base_output_dir=actual_output_dir)
                    self._log(f"Saving translated scene: Act {act}, Scene {scene}")
                    saver.save_scene(
                        act=act,
                        scene=scene,
                        translated_lines=translated_lines,
                        original_lines=modern_lines
                    )
                    
                    # Update scene info in the session
                    self._log("Updating session information")
                    update_scene_info(
                        translation_id=self.translation_id,
                        act=act,
                        scene=scene,
                        filename=os.path.basename(filepath),
                        line_count=len(translated_lines)
                    )
                    
                    self._log(f"Translation completed successfully. Saved to {actual_output_dir}")
                    return True, actual_output_dir, len(translated_lines)
                except Exception as save_error:
                    self._log(f"Error saving translation: {save_error}", "error")
                    return False, "", 0
            else:
                self._log("Error: Translator modules not available for saving", "error")
                return False, "", 0
                
        except Exception as e:
            self._log(f"Unexpected error in translate_file: {e}", "error")
            # Print stack trace for debugging
            import traceback
            self._log(f"Stack trace: {traceback.format_exc()}", "error")
            return False, "", 0
    
    def translate_uploaded_file(
        self, 
        uploaded_file, 
        temp_dir: str = "temp",
        output_dir: Optional[str] = None,
        force_retranslate: bool = False,
        use_hybrid_search: bool = True
    ) -> Tuple[bool, str, int]:
        """
        Translate an uploaded file from Streamlit.
        
        Args:
            uploaded_file: Streamlit UploadedFile object
            temp_dir: Directory to save the temporary file
            output_dir: Optional output directory
            force_retranslate: Force retranslation even if already translated
            use_hybrid_search: Whether to use hybrid search
            
        Returns:
            Tuple of (success, output_path, lines_translated)
        """
        if not self.translation_id:
            self._log("Error: No translation ID set for file translation")
            return False, "", 0
            
        if uploaded_file is None:
            self._log("Error: No file uploaded")
            return False, "", 0
            
        try:
            # Save the uploaded file temporarily
            ensure_directory(temp_dir)
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Translate the file
            success, out_dir, line_count = self.translate_file(
                filepath=temp_path,
                output_dir=output_dir,
                force_retranslate=force_retranslate,
                use_hybrid_search=use_hybrid_search
            )
            
            # Clean up temp file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as remove_error:
                self._log(f"Warning: Could not remove temporary file: {remove_error}")
            
            return success, out_dir, line_count
        except Exception as e:
            self._log(f"Error processing uploaded file: {e}")
            return False, "", 0
    
    def get_translation_status(self) -> Dict[str, Any]:
        """
        Get the current status of the translation session.
        
        Returns:
            Dictionary with status information
        """
        if not self.translation_id:
            return {
                "initialized": False,
                "translation_id": None,
                "scene_count": 0,
                "message": "No translation session active"
            }
        
        session_info = get_session_info(self.translation_id)
        
        return {
            "initialized": self.is_initialized,
            "translation_id": self.translation_id,
            "scene_count": len(session_info.get("scenes_translated", [])),
            "output_dir": session_info.get("output_dir", ""),
            "created_at": session_info.get("created_at", ""),
            "last_updated": session_info.get("last_updated", "")
        }


# Create a function to get a singleton instance
_INSTANCE: Optional[UITranslator] = None

def get_ui_translator(translation_id: Optional[str] = None, logger=None) -> UITranslator:
    """
    Get the UITranslator instance (singleton pattern).
    
    Args:
        translation_id: Optional translation session ID
        logger: Optional logger object
        
    Returns:
        UITranslator instance
    """
    global _INSTANCE
    
    if _INSTANCE is None:
        _INSTANCE = UITranslator(translation_id=translation_id, logger=logger)
    elif translation_id and _INSTANCE.translation_id != translation_id:
        _INSTANCE.set_translation_id(translation_id)
    
    return _INSTANCE