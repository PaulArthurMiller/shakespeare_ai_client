"""
Playwright Configuration Manager for Shakespeare AI.

This module handles configuration management for the playwright modules,
including loading and saving configuration settings.
"""
import os
from typing import Dict, Any

from modules.ui.file_helper import ensure_directory


class PlaywrightConfigManager:
    """
    Handles configuration management for the Shakespeare AI playwright.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the configuration manager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger
        self.config_path = "modules/playwright/config.py"
    
    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the provided logger if available."""
        if self.logger:
            if hasattr(self.logger, "_log"):
                self.logger._log(message, level)
            elif hasattr(self.logger, level):
                getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from the playwright config module.
        
        Returns:
            Configuration dictionary or default dict if not available
        """
        try:
            # Use dynamic import to avoid import errors if the module doesn't exist
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", self.config_path)
            if spec is None or spec.loader is None:
                self._log("Warning: Playwright config module not found", "warning")
                return self._get_default_config()
                
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)
            
            # Extract configuration variables
            config = {
                "model_provider": getattr(config_module, "model_provider", "anthropic"),
                "model_name": getattr(config_module, "model_name", "claude-3-7-sonnet-20250219"),
                "temperature": getattr(config_module, "temperature", 0.7),
                "random_seed": getattr(config_module, "random_seed", None)
            }
            
            return config
        except Exception as e:
            self._log(f"Error loading playwright configuration: {e}", "error")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration values.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "model_provider": "anthropic",
            "model_name": "claude-3-7-sonnet-20250219",
            "temperature": 0.7,
            "random_seed": None
        }
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """
        Update the playwright configuration.
        
        Args:
            config: Dictionary with configuration settings
                
        Returns:
            True if successful, False otherwise
        """
        try:
            self._log(f"Updating playwright configuration: {config}")
            
            # Load existing config to preserve any values not specified
            existing_config = self.load_config()
            
            # Update config with new values
            updated_config = existing_config.copy()
            for key, value in config.items():
                if value is not None:  # Only update if value is provided
                    updated_config[key] = value
            
            # Ensure the directory exists
            ensure_directory(os.path.dirname(self.config_path))
            
            # Generate the new config file content
            config_lines = [
                "# Configuration file for story generation and model settings",
                "import random" if updated_config.get("random_seed") is None else "",
                "",
                f"# Choose 'openai' or 'anthropic'",
                f"model_provider = \"{updated_config.get('model_provider', 'anthropic')}\"",
                "",
                f"# OpenAI model name (e.g., 'gpt-4o') or Anthropic (e.g., 'claude-3-7-sonnet-20250219')",
                f"model_name = \"{updated_config.get('model_name', 'claude-3-7-sonnet-20250219')}\"",
                "",
                f"# Controls creativity of the model. Range: 0.0 (deterministic) to 1.0 (very creative)",
                f"temperature = {updated_config.get('temperature', 0.7)}",
                "",
                "# Optional: Set a random seed for reproducibility - comment out the 'random' call and choose an integer for consistency."
            ]
            
            # Add the random seed line appropriately
            if "random_seed" in updated_config and updated_config["random_seed"] is not None:
                config_lines.append(f"random_seed = {updated_config['random_seed']}")
            else:
                config_lines.append("random_seed = random.randint(0, 999999)")
            
            # Join all lines into final content
            updated_content = "\n".join(config_lines)
            
            # Write to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
                
            self._log("Configuration updated successfully")
            return True
        except Exception as e:
            self._log(f"Error updating playwright configuration: {e}", "error")
            return False