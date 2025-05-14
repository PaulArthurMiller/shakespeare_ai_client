# Configuration file for story generation and model settings


# Choose 'openai' or 'anthropic'
model_provider = "anthropic"

# OpenAI model name (e.g., 'gpt-4o') or Anthropic (e.g., 'claude-3-7-sonnet-20250219')
model_name = "claude-3-7-sonnet-20250219"

# Controls creativity of the model. Range: 0.0 (deterministic) to 1.0 (very creative)
temperature = 0.7

# Optional: Set a random seed for reproducibility - comment out the 'random' call and choose an integer for consistency.
random_seed = 926656