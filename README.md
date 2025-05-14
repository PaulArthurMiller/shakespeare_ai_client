# Shakespeare AI

A modular application for translating modern English to Shakespearean style and generating Shakespeare-inspired plays.

## Features

- **Translator**: Convert modern English text to Shakespearean style using advanced AI
- **Playwright**: Generate original plays in Shakespearean style
- **Interactive UI**: User-friendly Streamlit interface

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Option 1: Simple Installation

1. Clone this repository:
   ```
   git clone https://github.com/your-username/shakespeare_ai.git
   cd shakespeare_ai
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Install the spaCy English model:
   ```
   python -m spacy download en_core_web_sm
   ```

### Option 2: Development Installation

1. Clone this repository:
   ```
   git clone https://github.com/your-username/shakespeare_ai.git
   cd shakespeare_ai
   ```

2. Install the package in development mode:
   ```
   pip install -e .
   ```

3. Install the spaCy English model:
   ```
   python -m spacy download en_core_web_sm
   ```

## Environment Setup

Create a `.env` file in the project root directory with your API keys:

```
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

## Usage

### Running the Streamlit UI

Launch the Streamlit user interface:

```
streamlit run streamlit_ui.py
```

The application will open in your default web browser.

### Using the Translator Module

The translator module converts modern English text to Shakespearean style:

1. Select "Translator" mode in the sidebar
2. Choose a translation mode (Full Play, Full Scene, or Section)
3. Upload a file or enter text directly
4. Click "Translate" to generate Shakespeare-style text

### Using the Playwright Module

The playwright module generates original plays in Shakespearean style:

1. Select "Playwright" mode in the sidebar
2. Define your characters and story structure
3. Generate the play structure and then individual scenes
4. Combine scenes into a complete play

## Project Structure

```
shakespeare_ai/
├── streamlit_ui.py              # Main Streamlit application
├── modules/
│   ├── ui/                      # UI-specific helper modules
│   ├── playwright/              # Play generation modules
│   ├── translator/              # Translation modules
│   └── utils/                   # Utility modules
└── data/                        # Data files and outputs
```

## License

[Your license information here]

## Contributing

[Your contribution guidelines here]

## Acknowledgments

- [Any acknowledgments or credits]