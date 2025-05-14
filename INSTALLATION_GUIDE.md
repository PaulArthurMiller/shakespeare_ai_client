# Shakespeare AI - Installation Guide

This guide will walk you through the simple process of installing and running the Shakespeare AI application on your system.

## System Requirements

- Windows 10 or 11, macOS 10.15+, or Linux
- Python 3.8 or higher
- 8GB RAM recommended
- Internet connection (for API access)

## Shakespeare AI Client - Quick Installation

1. Open terminal on the desktop (or in your preferred folder) and type:
   ```
   git --version
   ```
   If git is installed, you will see a version listed. If not, Mac will prompt you
   to install 'Xcode Command Line Tools', which includes git. Click 'Install' (this may
   take a few minutes.)
1. Once git is installed, clone this repository: 
   ```
   git clone https://github.com/PaulArthurMiller/shakespeare-ai-client.git
   ```
2. Change to directory: 
   ```
   cd shakespeare-ai-client
   ```
3. Run setup: 
   ```
   python3 client_setup.py
   ```
4. Follow the prompts to complete installation

## Step-by-Step Installation

### 1. Install Python (if not already installed)

#### For Windows:
1. Download the latest Python installer from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **Important**: Check the box "Add Python to PATH" during installation
4. Click "Install Now"
5. Verify installation by opening PowerShell and typing:
   ```
   python --version
   ```

#### For macOS:
1. Install using Homebrew:
   ```
   brew install python
   ```
2. Or download from [python.org](https://www.python.org/downloads/)

#### For Linux:
```
sudo apt update
sudo apt install python3 python3-pip
```

### 2. Download and Extract Shakespeare AI

#### Step 1: Download the Application
1. Go to the [releases page](https://github.com/PaulArthurMiller/shakespeare_ai/releases)
2. Download the latest client package (shakespeare_ai_v1.0.zip)
3. Extract the ZIP file to a location of your choice

#### Step 2: Run the Setup
1. Open PowerShell (Windows) or Terminal (Mac/Linux)
2. Navigate to the extracted folder:
   ```
   cd path\to\shakespeare_ai_client
   ```
3. Run the setup script:
   ```
   python client_setup.py
   ```

### 3. Set Up a Virtual Environment (Recommended)

#### Windows:
```
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux:
```
python -m venv venv
source venv/bin/activate
```

### 4. Install Required Packages

```
pip install -r requirements.txt
```

### 5. Install spaCy Language Model

```
python -m spacy download en_core_web_sm
```

### 6. Configure API Keys

1. Create a file named `.env` in the main project directory
2. Add your API keys to this file:
   ```
   OPENAI_API_KEY=your_openai_api_key
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

### 7. Set Up the Chroma Database

The application requires a pre-built vector database for RAG (Retrieval Augmented Generation) operations.

1. Download the Chroma database archive from https://drive.google.com/drive/folders/1C__VBv2IcjJOFdr6p9aWCoyhUwsGfucQ?usp=drive_link
2. Extract/copy the database to your Shakespeare AI installation:
   - Extract the ZIP file to a temporary location
   - Copy the entire `chromadb_vectors` folder to the `embeddings` directory in your Shakespeare AI installation
   - Final location should be: `shakespeare_ai/embeddings/chromadb_vectors/`
3. Verify the structure matches:

embeddings/
- chromadb_vectors/
   - 6787b5a8-d466-4980-81d1-04c63641edd9/
   - b737a7d0-f54f-42de-a7c2-ddf8036289d6/
   - f0c53ac0-5dd1-4531-acc8-2f6441273ba3/
   - chroma.sqlite3

## Important Notes

- The database is about 5.5 GB total
- Download time will depend on your internet connection
- Make sure you have sufficient disk space before downloading

## Running the Application

After installation, run the application with:

```
streamlit run streamlit_ui.py
```

The application should automatically open in your default web browser. If it doesn't, you can access it by navigating to:
```
http://localhost:8501
```

## Troubleshooting

### Common Issues:

1. **"Python command not found"**
   - Make sure Python is installed and added to your PATH
   - Try using `python3` instead of `python` on macOS/Linux

2. **"ImportError: No module found"**
   - Ensure you've activated the virtual environment
   - Try reinstalling dependencies: `pip install -r requirements.txt`

3. **"API Error"**
   - Check that your API keys are correctly set in the `.env` file
   - Verify your internet connection

4. **"ModuleNotFoundError: No module named 'en_core_web_sm'"**
   - Run: `python -m spacy download en_core_web_sm`

### Still Need Help?

If you encounter any issues during installation or runtime, please contact:
- Email: [paularthurmiller@gmail.com]
