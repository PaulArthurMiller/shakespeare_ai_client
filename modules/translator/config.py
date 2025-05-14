"""
Configuration file for the Shakespeare AI Translator module.
Contains settings for models, search parameters, and other configuration options.
"""

# Model settings
model_provider = "anthropic"  # Options: "anthropic", "openai"
model_name = "claude-3-7-sonnet-20250219"  # Will differ based on provider

# Model provider options
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

# LLM parameters
temperature = 0.7  # Controls creativity (0.0 to 1.0)

# RAG search settings
default_search_mode = "normal"  # Options: "normal", "hybrid"
default_top_k = 10  # Number of results to retrieve in search

# MMR diversity settings (used in selector.py)
mmr_lambda = 0.6  # Balance between relevance (1.0) and diversity (0.0)

# File paths
base_output_dir = "outputs/translated_scenes"  # Base directory - translation_id will be appended
translation_sessions_dir = "translation_sessions"

# Session settings
checkpoint_interval = 5  # Save checkpoint every N lines

# Validation is always enabled - core functionality of the app
validation_enabled = True

def get_output_dir(translation_id):
    """
    Get the output directory for a specific translation ID.
    
    Args:
        translation_id: The translation session ID
        
    Returns:
        String path to the output directory
    """
    import os
    output_dir = os.path.join(base_output_dir, translation_id)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def update_config(settings_dict):
    """
    Update configuration variables based on a dictionary of settings.
    
    Args:
        settings_dict: Dictionary containing configuration variables to update
    """
    # Get global variables
    global model_provider, model_name, temperature
    global default_search_mode, default_top_k, mmr_lambda
    global base_output_dir, checkpoint_interval
    
    # Update variables if they exist in settings_dict
    if "model_provider" in settings_dict:
        model_provider = settings_dict["model_provider"]
        
    if "model_name" in settings_dict:
        model_name = settings_dict["model_name"]
        
    if "temperature" in settings_dict:
        temperature = settings_dict["temperature"]
        
    if "default_search_mode" in settings_dict:
        default_search_mode = settings_dict["default_search_mode"]
        
    if "default_top_k" in settings_dict:
        default_top_k = settings_dict["default_top_k"]
        
    if "mmr_lambda" in settings_dict:
        mmr_lambda = settings_dict["mmr_lambda"]
        
    if "base_output_dir" in settings_dict:
        base_output_dir = settings_dict["base_output_dir"]
        
    if "checkpoint_interval" in settings_dict:
        checkpoint_interval = settings_dict["checkpoint_interval"]

def get_config():
    """
    Get the current configuration as a dictionary.
    
    Returns:
        Dictionary containing current configuration variables
    """
    return {
        "model_provider": model_provider,
        "model_name": model_name,
        "temperature": temperature,
        "default_search_mode": default_search_mode,
        "default_top_k": default_top_k,
        "mmr_lambda": mmr_lambda,
        "base_output_dir": base_output_dir,
        "checkpoint_interval": checkpoint_interval,
        "validation_enabled": validation_enabled
    }

def save_config_to_file(filepath="config.json"):
    """
    Save the current configuration to a JSON file.
    
    Args:
        filepath: Path to save the configuration file
    """
    import json
    import os
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Write config to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(get_config(), f, indent=2)

def load_config_from_file(filepath="config.json"):
    """
    Load configuration from a JSON file.
    
    Args:
        filepath: Path to the configuration file
    """
    import json
    import os
    
    if not os.path.exists(filepath):
        return
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        
        update_config(config_dict)
    except Exception as e:
        print(f"Error loading configuration: {e}")