"""
UI Configuration Manager for Shakespeare AI.

This module handles loading, saving, and managing configuration settings
for the Shakespeare AI UI, interfacing with both the translator and
playwright module configurations.
"""
import os
import json
from typing import Dict, Any, Optional, Union, List

# Import the translator config for direct integration
try:
    from modules.translator.config import (
        get_config as get_translator_config,
        update_config as update_translator_config,
        model_options
    )
    TRANSLATOR_CONFIG_AVAILABLE = True
except ImportError:
    print("Warning: Translator config module not found")
    TRANSLATOR_CONFIG_AVAILABLE = False
    model_options = {
        "anthropic": [
            "claude-3-7-sonnet-20250219",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229"
        ],
        "openai": [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4"
        ]
    }

# Configuration file locations
UI_CONFIG_PATH = "config/ui_settings.json"
PLAYWRIGHT_CONFIG_PATH = "modules/playwright/config.py"

# Default UI configuration
DEFAULT_UI_CONFIG = {
    "theme": "light",
    "default_mode": "Translator",  # or "Playwright"
    "log_level": "INFO",
    "save_logs": True,
    "auto_save": True,
    "last_translation_id": None,
    "last_output_dir": "outputs/translated_scenes",
    "max_history_items": 10
}


def ensure_config_dir():
    """Ensure the config directory exists."""
    os.makedirs(os.path.dirname(UI_CONFIG_PATH), exist_ok=True)


def load_ui_config() -> Dict[str, Any]:
    """
    Load UI configuration from the settings file.
    If the file doesn't exist, return default settings.
    """
    ensure_config_dir()
    
    if not os.path.exists(UI_CONFIG_PATH):
        return DEFAULT_UI_CONFIG.copy()
    
    try:
        with open(UI_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Update with any new default settings not in the loaded config
        for key, value in DEFAULT_UI_CONFIG.items():
            if key not in config:
                config[key] = value
                
        return config
    except Exception as e:
        print(f"Error loading UI configuration: {e}")
        return DEFAULT_UI_CONFIG.copy()


def save_ui_config(config: Dict[str, Any]) -> bool:
    """
    Save UI configuration to the settings file.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if successful, False otherwise
    """
    ensure_config_dir()
    
    try:
        with open(UI_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving UI configuration: {e}")
        return False


def update_ui_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update UI configuration with new values.
    
    Args:
        updates: Dictionary of settings to update
        
    Returns:
        Updated configuration dictionary
    """
    config = load_ui_config()
    config.update(updates)
    save_ui_config(config)
    return config


def get_model_options() -> Dict[str, List[str]]:
    """
    Get available model options for each provider.
    
    Returns:
        Dictionary mapping provider names to lists of model names
    """
    if TRANSLATOR_CONFIG_AVAILABLE:
        # Return the model options directly from the translator config
        return model_options
    else:
        # Return a default set of options
        return {
            "anthropic": [
                "claude-3-7-sonnet-20250219",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229"
            ],
            "openai": [
                "gpt-4o",
                "gpt-4-turbo",
                "gpt-4"
            ]
        }


def load_playwright_config() -> Dict[str, Any]:
    """
    Load configuration from the playwright config module.
    This uses a different approach since the playwright config is a Python module.
    
    Returns:
        Configuration dictionary or empty dict if not available
    """
    try:
        # Use dynamic import to avoid import errors if the module doesn't exist
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", PLAYWRIGHT_CONFIG_PATH)
        if spec is None or spec.loader is None:
            print("Warning: Playwright config module not found")
            return {}
            
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
        print(f"Error loading playwright configuration: {e}")
        return {}


def save_playwright_config(config: Dict[str, Any]) -> bool:
    """
    Save configuration to the playwright config module.
    This creates/updates the Python file directly.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(PLAYWRIGHT_CONFIG_PATH), exist_ok=True)
        
        # Check if file exists to preserve any custom code
        has_existing = os.path.exists(PLAYWRIGHT_CONFIG_PATH)
        existing_content = ""
        
        if has_existing:
            with open(PLAYWRIGHT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        
        # Generate the new config file with most current settings
        config_lines = [
            "# Configuration file for story generation and model settings",
            "import random" if config.get("random_seed") is None else "",
            "",
            f"# Choose 'openai' or 'anthropic'",
            f"model_provider = \"{config.get('model_provider', 'anthropic')}\"",
            "",
            f"# OpenAI model name (e.g., 'gpt-4o') or Anthropic (e.g., 'claude-3-7-sonnet-20250219')",
            f"model_name = \"{config.get('model_name', 'claude-3-7-sonnet-20250219')}\"",
            "",
            f"# Controls creativity of the model. Range: 0.0 (deterministic) to 1.0 (very creative)",
            f"temperature = {config.get('temperature', 0.7)}",
            "",
            "# Optional: Set a random seed for reproducibility - comment out the 'random' call and choose an integer for consistency."
        ]
        
        # Add the random seed line appropriately
        if "random_seed" in config and config["random_seed"] is not None:
            config_lines.append(f"random_seed = {config['random_seed']}")
        else:
            config_lines.append("random_seed = random.randint(0, 999999)")
        
        # Join all lines into final content
        updated_content = "\n".join(config_lines)
        
        # Write to file
        with open(PLAYWRIGHT_CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write(updated_content)
            
        return True
    except Exception as e:
        print(f"Error saving playwright configuration: {e}")
        return False


def load_translator_config() -> Dict[str, Any]:
    """
    Load configuration from the translator config module.
    
    Returns:
        Configuration dictionary or default dict if not available
    """
    if TRANSLATOR_CONFIG_AVAILABLE:
        return get_translator_config()
    else:
        # Return a default translator configuration
        return {
            "model_provider": "anthropic",
            "model_name": "claude-3-7-sonnet-20250219",
            "temperature": 0.7,
            "default_search_mode": "normal",
            "default_top_k": 10,
            "mmr_lambda": 0.6,
            "base_output_dir": "outputs/translated_scenes",
            "checkpoint_interval": 5,
            "validation_enabled": True
        }


def save_translator_config(config: Dict[str, Any]) -> bool:
    """
    Save configuration to the translator config module.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if successful, False otherwise
    """
    if TRANSLATOR_CONFIG_AVAILABLE:
        try:
            update_translator_config(config)
            return True
        except Exception as e:
            print(f"Error saving translator configuration: {e}")
            return False
    else:
        print("Warning: Cannot save translator configuration - module not available")
        return False


def get_ui_preferences() -> Dict[str, Any]:
    """
    Get user preferences specific to the UI.
    
    Returns:
        Dictionary of UI preferences
    """
    config = load_ui_config()
    return {
        "theme": config.get("theme", "light"),
        "default_mode": config.get("default_mode", "Translator"),
        "auto_save": config.get("auto_save", True)
    }


# Helper function to get the most appropriate model name based on provider
def get_default_model_for_provider(provider: str) -> str:
    """
    Get the default model name for a given provider.
    
    Args:
        provider: Provider name ("anthropic" or "openai")
        
    Returns:
        Default model name for the provider
    """
    options = get_model_options()
    if provider in options and options[provider]:
        return options[provider][0]  # Return the first model in the list
    
    # Fallbacks
    if provider == "anthropic":
        return "claude-3-7-sonnet-20250219"
    elif provider == "openai":
        return "gpt-4o"
    else:
        return "claude-3-7-sonnet-20250219"  # Default fallback