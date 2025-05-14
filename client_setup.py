"""
Client setup script for Shakespeare AI.
Run this after extracting the ZIP package.
"""
import os
import sys
import subprocess
import urllib.request
import zipfile
from pathlib import Path

def check_python_version():
    """Check if Python version is sufficient."""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required.")
        return False
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def setup_virtual_environment():
    """Create and activate virtual environment."""
    print("\nSetting up virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", "venv"])
    
    if sys.platform == "win32":
        pip_path = "venv\\Scripts\\pip"
        python_path = "venv\\Scripts\\python"
    else:
        pip_path = "venv/bin/pip"
        python_path = "venv/bin/python"
    
    return pip_path, python_path

def install_dependencies(pip_path, python_path):
    """Install required packages."""
    print("\nInstalling dependencies...")
    subprocess.run([pip_path, "install", "-r", "requirements.txt"])
    print("\nInstalling spaCy...")
    subprocess.run([pip_path, "install", "spacy"])
    print("Installing spaCy model...")
    subprocess.run([python_path, "-m", "spacy", "download", "en_core_web_sm"])

def setup_env_file():
    """Create .env file if it doesn't exist."""
    if not os.path.exists(".env"):
        print("\nCreating .env file template...")
        with open(".env", "w") as f:
            f.write("# Add your API keys here\n")
            f.write("OPENAI_API_KEY=your_openai_api_key_here\n")
            f.write("ANTHROPIC_API_KEY=your_anthropic_api_key_here\n")
        print("✓ Created .env template")
    else:
        print("✓ .env file already exists")

def check_database():
    """Check if the Chroma database exists."""
    db_path = Path("embeddings/chromadb_vectors")
    if db_path.exists() and any(db_path.iterdir()):
        print("✓ Chroma database found")
        return True
    else:
        print("⚠ Chroma database not found")
        return False

def main():
    print("=== Shakespeare AI Client Setup ===\n")
    
    # Check Python
    if not check_python_version():
        return
    
    # Set up virtual environment
    pip_path, python_path = setup_virtual_environment()
    
    # Install dependencies
    install_dependencies(pip_path, python_path)
    
    # Set up .env file
    setup_env_file()
    
    # Check database
    db_exists = check_database()
    
    print("\n=== Setup Complete ===")
    print("\nNext steps:")
    print("1. Edit .env file with your API keys")
    if not db_exists:
        print("2. Download and extract the Chroma database to embeddings/chromadb_vectors/")
        print("   (You should have received a Dropbox link for this)")
    print("3. Run the application:")
    if sys.platform == "win32":
        print("   venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    print("   streamlit run streamlit_ui.py")

if __name__ == "__main__":
    main()