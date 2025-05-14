import streamlit as st
import uuid
import os
import re
import json
import time
from typing import Optional, Dict, List, Any, Union
from pathlib import Path
from datetime import datetime
import shutil  # For file operations

# Import your existing modules
from modules.playwright.story_expander import StoryExpander
from modules.playwright.scene_writer import SceneWriter
from modules.translator.translation_manager import TranslationManager
from modules.translator.scene_saver import SceneSaver
from modules.utils.logger import CustomLogger
from modules.ui.playwright.ui_playwright import get_ui_playwright
from modules.ui.ui_translator import get_ui_translator

from modules.ui.file_helper import (
    load_text_from_file, 
    save_text_to_file, 
    ensure_directory,
    extract_act_scene_from_filename,
    parse_markdown_scene
)

from modules.ui.session_manager import (
    get_session_info,
    update_scene_info,
    is_scene_translated,
    create_new_session,
    get_all_sessions 
)

# Initialize session state
if "mode" not in st.session_state:
    st.session_state.mode = "Playwright"
if "translation_id" not in st.session_state:
    st.session_state.translation_id = None
if "current_line_index" not in st.session_state:
    st.session_state.current_line_index = 0
if "translated_lines" not in st.session_state:
    st.session_state.translated_lines = []
if "modern_lines" not in st.session_state:
    st.session_state.modern_lines = []
    
# New session states for the project-based UI
if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = None
if "show_export_options" not in st.session_state:
    st.session_state.show_export_options = False
if "generated_full_play" not in st.session_state:
    st.session_state.generated_full_play = False
if "last_generated_scene" not in st.session_state:
    st.session_state.last_generated_scene = None

# Initialize session state for translation control
if "translation_active" not in st.session_state:
    st.session_state.translation_active = False
if "cancel_requested" not in st.session_state:
    st.session_state.cancel_requested = False

# Set page config
st.set_page_config(
    page_title="Shakespeare AI",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize logger
logger = CustomLogger("StreamlitUI")

# Helper functions for file operations and session management
def load_existing_translation_ids():
    """Get a list of existing translation IDs from the translation_sessions directory."""
    try:
        path = Path("translation_sessions")
        if not path.exists():
            return []
        
        translation_info_files = list(path.glob("*_translation_info.json"))
        translations = []
        
        for file in translation_info_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                    translations.append({
                        "id": info.get("translation_id", "unknown"),
                        "created_at": info.get("created_at", "unknown"),
                        "scenes_count": len(info.get("scenes_translated", [])),
                        "last_updated": info.get("last_updated", "")
                    })
            except Exception as e:
                st.error(f"Error loading translation info from {file}: {e}")
        
        # Sort by last updated, newest first
        translations.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
        return translations
    except Exception as e:
        st.error(f"Error loading translation IDs: {e}")
        return []

def generate_new_translation_id():
    """Generate a new translation ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    random_part = str(uuid.uuid4())[:6]
    return f"trans_{timestamp}_{random_part}"

# Sidebar - Mode Selection
with st.sidebar:
    st.title("Shakespeare AI")
    
    mode = st.radio("Mode", ["Playwright", "Translator"])

    # Check if mode has changed and update session state
    if "mode" in st.session_state and st.session_state.mode != mode:
        # Mode has changed - clean up previous mode resources if needed
        st.session_state.mode = mode
        
        # Initialize appropriate mode
        if mode == "Translator":
            st.session_state.logger = CustomLogger("Translator_UI", log_level="DEBUG")
            st.session_state.logger.info(f"Switching to Translator mode")
            
            # Clear any previous translator state
            if "translation_manager" in st.session_state:
                del st.session_state.translation_manager
    else:
        # First time or no change
        st.session_state.mode = mode    

    st.divider()
    
    if mode == "Playwright":
        st.subheader("Playwright Settings")
        model_provider = st.selectbox(
            "Model Provider", 
            ["anthropic", "openai"]
        )
        
        if model_provider == "anthropic":
            model_name = st.selectbox(
                "Model", 
                ["claude-3-7-sonnet-20250219", "claude-3-opus-20240229", "claude-3-sonnet-20240229"]
            )
        else:
            model_name = st.selectbox(
                "Model", 
                ["gpt-4o", "gpt-4-turbo", "gpt-4"]
            )
        
        creativity = st.slider(
            "Creativity", 
            min_value=0.0, 
            max_value=1.0, 
            value=0.7, 
            step=0.1
        )
        
        length_guide = st.slider(
            "Length", 
            min_value=1, 
            max_value=3, 
            value=2, 
            help="1 = Shorter (600-800 words), 2 = Medium (900-1100 words), 3 = Longer (1200-1500 words)"
        )
    
    elif mode == "Translator":
        st.subheader("Translator Settings")
        
        # Model selection for translator
        model_provider = st.selectbox(
            "Model Provider", 
            ["anthropic", "openai"],
            key="translator_model_provider"
        )
        
        if model_provider == "anthropic":
            model_name = st.selectbox(
                "Model", 
                ["claude-3-7-sonnet-20250219", "claude-3-opus-20240229", "claude-3-sonnet-20240229"],
                key="translator_model_name"
            )
        else:
            model_name = st.selectbox(
                "Model", 
                ["gpt-4o", "gpt-4-turbo", "gpt-4"],
                key="translator_model_name"
            )
        
        # Translation ID management
        st.subheader("Translation Session")
        
        translation_option = st.radio(
            "Translation ID", 
            ["Create New", "Use Existing"]
        )
        
        if translation_option == "Create New":
            if st.button("Generate New Translation ID"):
                # Create a new ID
                new_id = generate_new_translation_id()
                st.session_state.translation_id = new_id
                
                # Log the new ID creation
                if "logger" in st.session_state:
                    st.session_state.logger.info(f"Created new Translation ID: {new_id}")
                
                # Clear any existing translator in session
                if "ui_translator" in st.session_state:
                    del st.session_state.ui_translator
                    
                st.success(f"New Translation ID: {new_id}")
                
                # Force a rerun to update UI
                st.rerun()
        else:
            # Load existing translation IDs
            existing_translations = load_existing_translation_ids()
            
            if not existing_translations:
                st.warning("No existing translations found")
            else:
                translation_options = {
                    f"{t['id']} ({t['created_at'][:10]}, {t['scenes_count']} scenes)": t['id'] 
                    for t in existing_translations
                }
                
                selected_translation = st.selectbox(
                    "Select Translation ID",
                    options=list(translation_options.keys())
                )
                
                if selected_translation:
                    selected_id = translation_options[selected_translation]
                    
                    # Only update if ID has changed
                    if st.session_state.get("translation_id") != selected_id:
                        st.session_state.translation_id = selected_id
                        
                        # Log the ID selection
                        if "logger" in st.session_state:
                            st.session_state.logger.info(f"Selected Translation ID: {selected_id}")
                        
                        # Clear any existing translator in session
                        if "ui_translator" in st.session_state:
                            del st.session_state.ui_translator
                            
                        st.info(f"Using Translation ID: {selected_id}")
                        
                        # Force a rerun to update UI with the new ID
                        st.rerun()

# Main content area
if st.session_state.mode == "Playwright":
    st.title("Playwright Mode")
    
    # Add tabs for different operations
    tabs = st.tabs(["Create Project", "Add Scene", "Generate Scene", "Export"])
    
    # Tab 1: Create Project
    with tabs[0]:
        st.header("Create a New Play Project")
        
        with st.form("create_project_form"):
            play_title = st.text_input("Play Title", "My Modern Play")
            
            # Thematic guidelines
            thematic_guidelines = st.text_area(
                "Thematic Guidelines",
                "A modern retelling that explores themes of ambition, betrayal, and redemption.",
                height=150,
                help="Overall thematic guidance for the entire play"
            )
            
            # Character voices input
            st.subheader("Character Voices")
            
            num_characters = st.number_input("Number of Characters", min_value=1, max_value=10, value=3)
            
            character_voices = {}
            for i in range(num_characters):
                col1, col2 = st.columns(2)
                with col1:
                    char_name = st.text_input(f"Character {i+1} Name", key=f"char_name_{i}")
                with col2:
                    char_desc = st.text_input(f"Character {i+1} Voice", 
                                            key=f"char_desc_{i}", 
                                            help="Describe how this character speaks")
                if char_name:
                    character_voices[char_name] = char_desc
            
            # Create project button
            submit_project = st.form_submit_button("Create Project")
        
        if submit_project:
            if not character_voices:
                st.error("Please add at least one character")
            else:
                with st.spinner("Creating project..."):
                    try:
                        # Get UI playwright instance
                        playwright = get_ui_playwright(logger=st.session_state.get("logger"))
                        
                        # Update the configuration
                        config = {
                            "model_provider": model_provider,
                            "model_name": model_name,
                            "temperature": creativity
                        }
                        playwright.update_playwright_config(config)
                        
                        # Create the project
                        project_id = playwright.manage_project_creation(
                            title=play_title,
                            thematic_guidelines=thematic_guidelines,
                            character_voices=character_voices
                        )
                        
                        # Store project_id in session state
                        st.session_state.current_project_id = project_id
                        
                        st.success(f"Project created successfully! Project ID: {project_id}")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error creating project: {e}")
    
    # Tab 2: Add Scene
    with tabs[1]:
        st.header("Add Scene to Project")
        
        # Check if we have a current project
        if not st.session_state.get("current_project_id"):
            # No current project, allow selection from existing projects
            playwright = get_ui_playwright(logger=st.session_state.get("logger"))
            projects = playwright.get_project_list()
            
            if not projects:
                st.warning("No projects found. Create a project first.")
            else:
                project_options = {p["title"] + " (" + p["id"] + ")": p["id"] for p in projects}
                selected_project = st.selectbox(
                    "Select Project",
                    options=list(project_options.keys())
                )
                
                if selected_project:
                    st.session_state.current_project_id = project_options[selected_project]
                    st.success(f"Selected project: {selected_project}")
        
        # If we have a project (either selected or created), show the add scene form
        if st.session_state.get("current_project_id"):
            project_id: Optional[str] = st.session_state.current_project_id
            if project_id is None:
                st.error("⚠️ No project selected. Please create or select a project first.")
                st.stop()  # This stops execution of the Streamlit app at this point

            # Get project data to show metadata and available characters
            playwright = get_ui_playwright(logger=st.session_state.get("logger"))
            project_data = playwright.get_project_details(project_id)
            
            if project_data:
                st.subheader(f"Project: {project_data.get('title', 'Unnamed')}")
                st.write(f"Characters: {', '.join(project_data.get('character_voices', {}).keys())}")
                
                with st.form("add_scene_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        act = st.text_input("Act", "I", help="Act number (e.g., I, II, III or 1, 2, 3)")
                    with col2:
                        scene = st.text_input("Scene", "1", help="Scene number (e.g., 1, 2, 3)")
                    
                    # Scene overview
                    overview = st.text_area(
                        "Scene Overview",
                        "Scene description here...",
                        height=150,
                        help="Describe what happens in this scene"
                    )
                    
                    # Scene setting
                    setting = st.text_area(
                        "Setting",
                        "Describe the setting...",
                        height=100,
                        help="Physical location and atmosphere of the scene"
                    )
                    
                    # Characters in scene
                    all_characters = list(project_data.get("character_voices", {}).keys())
                    scene_characters = st.multiselect(
                        "Characters in Scene",
                        options=all_characters,
                        default=all_characters[:2] if len(all_characters) >= 2 else all_characters
                    )
                    
                    # Additional instructions
                    additional_instructions = st.text_area(
                        "Additional Instructions (Optional)",
                        "",
                        height=100,
                        help="Any special notes for this scene"
                    )
                    
                    # Submit button
                    submit_scene = st.form_submit_button("Add Scene")
                
                if submit_scene:
                    if not overview or not setting or not scene_characters:
                        st.error("Please fill in all required fields")
                    else:
                        with st.spinner("Adding scene to project..."):
                            try:
                                success = playwright.manage_scene_addition(
                                    project_id=project_id,
                                    act=act,
                                    scene=scene,
                                    overview=overview,
                                    setting=setting,
                                    characters=scene_characters,
                                    additional_instructions=additional_instructions
                                )
                                
                                if success:
                                    st.success(f"Scene {act}.{scene} added successfully!")
                                else:
                                    st.error("Failed to add scene")
                            except Exception as e:
                                st.error(f"Error adding scene: {e}")
    
    # Tab 3: Generate Scene
    with tabs[2]:
        st.header("Generate Scene")
        
        # Check if we have a current project
        if not st.session_state.get("current_project_id"):
            # No current project, allow selection from existing projects
            playwright = get_ui_playwright(logger=st.session_state.get("logger"))
            projects = playwright.get_project_list()
            
            if not projects:
                st.warning("No projects found. Create a project first.")
            else:
                project_options = {p["title"] + " (" + p["id"] + ")": p["id"] for p in projects}
                selected_project = st.selectbox(
                    "Select Project",
                    options=list(project_options.keys()),
                    key="gen_project_select"
                )
                
                if selected_project:
                    st.session_state.current_project_id = project_options[selected_project]
                    st.success(f"Selected project: {selected_project}")
        
        # If we have a project, show scene generation options
        if st.session_state.get("current_project_id"):
            project_id: Optional[str] = st.session_state.current_project_id
            if project_id is None:
                st.error("⚠️ No project selected. Please create or select a project first.")
                st.info("Use the 'Create Project' tab to create a new project or select an existing one.")
                st.stop()  # This stops execution of the Streamlit app at this point

            # Get project data
            playwright = get_ui_playwright(logger=st.session_state.get("logger"))
            project_data = playwright.get_project_details(project_id)
            
            if project_data:
                st.subheader(f"Project: {project_data.get('title', 'Unnamed')}")
                
                # Get defined scenes
                scenes = project_data.get("scenes", [])
                
                if not scenes:
                    st.warning("No scenes defined in this project. Please add a scene first.")
                else:
                    # Allow user to select a scene or generate all
                    scene_options = [f"Act {s['act']}, Scene {s['scene']}" for s in scenes]
                    scene_options.insert(0, "Generate All Scenes")
                    
                    selected_option = st.selectbox(
                        "Select Scene to Generate",
                        options=scene_options
                    )
                    
                    # Scene length option
                    length_option = st.select_slider(
                        "Scene Length",
                        options=["short", "medium", "long"],
                        value="medium",
                        help="short (600-800 words), medium (900-1100 words), long (1200-1500 words)"
                    )
                    
                    # Generate button
                    if st.button("Generate Scene(s)"):
                        if selected_option == "Generate All Scenes":
                            # Generate all scenes
                            with st.spinner("Generating all scenes... This may take a while."):
                                try:
                                    success, result = playwright.generate_complete_project(
                                        project_id=project_id,
                                        length_option=length_option
                                    )
                                    
                                    if success:
                                        st.success("All scenes generated successfully!")
                                        st.info(f"Combined play saved to: {result}")
                                        
                                        # Display a clickable link to open the file location
                                        if os.path.exists(result):
                                            directory = os.path.dirname(result)
                                            st.markdown(f"**Output location:** `{directory}`")
                                            
                                            # Read a snippet of the generated play
                                            try:
                                                with open(result, 'r', encoding='utf-8') as f:
                                                    play_content = f.read()
                                                    # Display a preview of the play (first 500 chars)
                                                    st.text_area("Preview of generated play", 
                                                                play_content[:500] + "...", 
                                                                height=200)
                                            except:
                                                pass
                                        
                                        # Show option to export
                                        st.session_state.show_export_options = True
                                        st.session_state.generated_full_play = True
                                        # Add a button to jump to export tab
                                        if st.button("Go to Export Options"):
                                            st.rerun()
                                    else:
                                        st.error(f"Error generating scenes: {result}")
                                        st.warning("Please check the logs for more information.")
                                except Exception as e:
                                    st.error(f"Error generating scenes: {e}")
                                    st.warning("Please check the logs for more information.")
                        else:
                            # Generate specific scene
                            scene_idx = scene_options.index(selected_option) - 1  # Adjust for "Generate All" option
                            scene_data = scenes[scene_idx]
                            
                            with st.spinner(f"Generating Act {scene_data['act']}, Scene {scene_data['scene']}..."):
                                try:
                                    progress_bar = st.progress(0)
                                    status_text = st.empty()
                                    
                                    # Update status periodically to show activity
                                    status_text.text("Initializing scene generation...")
                                    progress_bar.progress(10)
                                    
                                    # Start generation
                                    status_text.text("Creating scene expansion...")
                                    progress_bar.progress(30)
                                    
                                    # This part is actually doing the work
                                    success, content, scene_path = playwright.generate_single_scene(
                                        project_id=project_id,
                                        act=scene_data['act'],
                                        scene=scene_data['scene'],
                                        length_option=length_option
                                    )
                                    
                                    # Update progress
                                    status_text.text("Finalizing scene...")
                                    progress_bar.progress(90)
                                    
                                    if success:
                                        progress_bar.progress(100)
                                        status_text.text("Scene generation completed!")
                                        st.success(f"Scene generated successfully!")
                                        
                                        # Display the generated scene
                                        st.text_area("Generated Scene", content, height=400)
                                        
                                        # Display file location
                                        if os.path.exists(scene_path):
                                            directory = os.path.dirname(scene_path)
                                            st.markdown(f"**Output location:** `{directory}`")
                                        
                                        # Store the scene info for export
                                        st.session_state.last_generated_scene = {
                                            "project_id": project_id,
                                            "act": scene_data['act'],
                                            "scene": scene_data['scene'],
                                            "path": scene_path
                                        }
                                        
                                        # Show export options
                                        st.session_state.show_export_options = True
                                        st.session_state.generated_full_play = False
                                        # Add a button to jump to export tab
                                        if st.button("Go to Export Options"):
                                            st.rerun()
                                    else:
                                        progress_bar.progress(0)
                                        status_text.text("Scene generation failed.")
                                        st.error(f"Error generating scene: {content}")
                                        st.warning("Please check the logs for more information.")
                                except Exception as e:
                                    st.error(f"Error generating scene: {e}")
                                    st.warning("Please check the logs for more information.")
    
    # Tab 4: Export
    with tabs[3]:
        st.header("Export Play")
        
        # Check if we have content to export
        if not st.session_state.get("current_project_id"):
            st.warning("No active project. Please create or select a project first.")
        elif not st.session_state.get("show_export_options", False):
            st.info("Generate a scene or full play first to enable export options.")
        else:
            project_id: Optional[str] = st.session_state.current_project_id
            if project_id is None:
                st.error("⚠️ No project selected. Please create or select a project first.")
                st.info("Create a project in the 'Create Project' tab before generating scenes.")
                st.stop()  # This stops execution of the Streamlit app at this point            

            # Get project data
            playwright = get_ui_playwright(logger=st.session_state.get("logger"))
            project_data = playwright.get_project_details(project_id)
            
            if project_data:
                st.subheader(f"Project: {project_data.get('title', 'Unnamed')}")
                
                # Export format options
                export_format = st.radio(
                    "Export Format",
                    options=["DOCX", "Markdown"],
                    index=0,
                    horizontal=True
                )
                
                # What to export
                if st.session_state.get("generated_full_play", False):
                    # Full play was generated
                    if st.button("Export Full Play"):
                        with st.spinner(f"Exporting play as {export_format}..."):
                            try:
                                success, output_path = playwright.export_full_play_file(
                                    project_id=project_id,
                                    output_format=export_format.lower()
                                )
                                
                                if success:
                                    st.success(f"Play exported successfully!")
                                    st.info(f"Saved to: {output_path}")
                                    
                                    # Provide download link if possible
                                    if os.path.exists(output_path):
                                        with open(output_path, "rb") as f:
                                            file_contents = f.read()
                                        
                                        extension = ".docx" if export_format.lower() == "docx" else ".md"
                                        filename = f"{project_data.get('title', 'play').replace(' ', '_')}{extension}"
                                        
                                        st.download_button(
                                            label="Download File",
                                            data=file_contents,
                                            file_name=filename,
                                            mime="application/octet-stream"
                                        )
                                else:
                                    st.error(f"Error exporting play: {output_path}")
                            except Exception as e:
                                st.error(f"Error exporting play: {e}")
                else:
                    # Single scene was generated
                    last_scene = st.session_state.get("last_generated_scene", {})
                    
                    if last_scene and st.button("Export Scene"):
                        with st.spinner(f"Exporting scene as {export_format}..."):
                            try:
                                success, output_path = playwright.export_scene_file(
                                    project_id=project_id,
                                    act=last_scene['act'],
                                    scene=last_scene['scene'],
                                    output_format=export_format.lower()
                                )
                                
                                if success:
                                    st.success(f"Scene exported successfully!")
                                    st.info(f"Saved to: {output_path}")
                                    
                                    # Provide download link if possible
                                    if os.path.exists(output_path):
                                        with open(output_path, "rb") as f:
                                            file_contents = f.read()
                                        
                                        extension = ".docx" if export_format.lower() == "docx" else ".md"
                                        filename = f"act_{last_scene['act'].lower()}_scene_{last_scene['scene'].lower()}{extension}"
                                        
                                        st.download_button(
                                            label="Download File",
                                            data=file_contents,
                                            file_name=filename,
                                            mime="application/octet-stream"
                                        )
                                else:
                                    st.error(f"Error exporting scene: {output_path}")
                            except Exception as e:
                                st.error(f"Error exporting scene: {e}")

elif st.session_state.mode == "Translator":
    st.title("Translator Mode")
    
    # Ensure we have a logger for translator mode
    if "logger" not in st.session_state:
        st.session_state.logger = CustomLogger("Translator_UI", log_level="DEBUG")
        st.session_state.logger.info("Initializing Translator mode logger")
    
    if not st.session_state.translation_id:
        st.warning("Please create or select a Translation ID in the sidebar first.")
    else:
        st.info(f"Using Translation ID: {st.session_state.translation_id}")
        
        # Explicitly initialize UITranslator with the current translation ID and logger
        if "ui_translator" not in st.session_state:
            with st.spinner("Initializing translator..."):
                try:
                    # Create a dedicated file logger for debugging
                    debug_logger = CustomLogger("Translator_Debug", log_level="DEBUG", 
                                              log_file=f"logs/translator_debug_{st.session_state.translation_id}.log")
                    debug_logger.info(f"Initializing UITranslator with ID: {st.session_state.translation_id}")
                    
                    # Initialize UITranslator
                    ui_translator = get_ui_translator(
                        translation_id=st.session_state.translation_id,
                        logger=debug_logger
                    )
                    
                    # Ensure initialization is complete
                    success = ui_translator.initialize()
                    if success:
                        st.session_state.ui_translator = ui_translator
                        debug_logger.info("UITranslator successfully initialized")
                    else:
                        st.error("Failed to initialize translator. Check the logs for details.")
                        debug_logger.error("Failed to initialize UITranslator")
                except Exception as e:
                    st.error(f"Error initializing translator: {e}")
                    if "logger" in st.session_state:
                        st.session_state.logger.error(f"Error initializing UITranslator: {e}")
        
        # Translation mode selection
        translation_mode = st.radio(
            "Translation Mode",
            ["Full Play", "Full Scene", "Section"]
        )
        
        use_hybrid_search = st.checkbox("Use Hybrid Search", value=True, 
                                        help="Combines vector and keyword search for better results")
        
        if translation_mode == "Full Play":
            st.subheader("Full Play Translation")
            
            # File uploader for play script
            uploaded_file = st.file_uploader("Upload Play Script (Markdown)", type="md")
            
            if uploaded_file:
                st.success(f"Uploaded: {uploaded_file.name}")
                
                # Output directory selection
                output_dir = st.text_input("Output Directory", "outputs/translated_play")
                
                # Make sure we have a ui_translator in the session
                if "ui_translator" not in st.session_state:
                    st.error("Translator not initialized. Please refresh the page and try again.")
                # Check if translation is already active
                elif st.session_state.translation_active:
                    # Display progress information
                    st.info("Translation is in progress...")
                    
                    # Display cancel button
                    if st.button("Cancel Translation"):
                        st.session_state.cancel_requested = True
                        st.warning("Cancel requested. Translation will stop after current line completes...")
                elif st.button("Start Translation"):
                    # Reset cancellation flag
                    st.session_state.cancel_requested = False
                    # Set active flag
                    st.session_state.translation_active = True
                    
                    # Create a dedicated logger for full play translation
                    debug_logger = CustomLogger("Full_Play_Translation", log_level="DEBUG", 
                                            log_file=f"logs/full_play_{st.session_state.translation_id}.log")
                    debug_logger.info(f"Starting full play translation for file: {uploaded_file.name}")
                    
                    with st.spinner("Translating play... This may take several minutes."):
                        try:
                            # Save uploaded file temporarily
                            temp_dir = "temp_uploads"
                            os.makedirs(temp_dir, exist_ok=True)
                            temp_path = os.path.join(temp_dir, uploaded_file.name)
                            
                            with open(temp_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            
                            debug_logger.info(f"Saved uploaded file to temporary location: {temp_path}")
                            debug_logger.info(f"File size: {os.path.getsize(temp_path)} bytes")
                            
                            # Use the ui_translator from the session state
                            ui_translator = st.session_state.ui_translator
                            
                            # Create containers for progress display
                            progress_bar = st.progress(0)
                            status_message = st.empty()
                            cancel_button_container = st.empty()
                            
                            # Add a cancel button inside the processing loop
                            if cancel_button_container.button("Stop Translation", key="cancel_during_process"):
                                st.session_state.cancel_requested = True
                                status_message.warning("Cancellation requested. Finishing current processing...")
                            
                            status_message.info("Analyzing play file...")
                            progress_bar.progress(10)
                            
                            # Check for cancellation
                            if st.session_state.cancel_requested:
                                status_message.warning("Translation cancelled by user")
                                debug_logger.info("Translation cancelled by user")
                                st.session_state.translation_active = False
                                st.session_state.cancel_requested = False
                                st.rerun()
                            
                            # Determine if it's a single scene or multiple scenes
                            debug_logger.info("Analyzing file to determine if it's a single scene or full play")
                            
                            # ... (rest of analysis code)
                            
                            # Ensure translator is initialized
                            if not ui_translator.is_initialized:
                                debug_logger.warning("Translator not initialized. Attempting to initialize...")
                                success = ui_translator.initialize()
                                if not success:
                                    st.error("Failed to initialize translator. Please try again.")
                                    debug_logger.error("Failed to initialize translator")
                                    st.session_state.translation_active = False
                                    st.stop()
                            
                            # Update status before translation
                            status_message.info("Starting translation... (Click 'Stop Translation' to cancel)")
                            progress_bar.progress(30)
                            
                            # Check for cancellation again
                            if st.session_state.cancel_requested:
                                status_message.warning("Translation cancelled by user")
                                debug_logger.info("Translation cancelled by user")
                                st.session_state.translation_active = False
                                st.session_state.cancel_requested = False
                                st.rerun()
                            
                            # Custom translation process with cancellation support
                            # Instead of directly calling translate_file, we'll implement a cancellable version
                            
                            # Parse the file to get dialogue lines
                            modern_lines = parse_markdown_scene(temp_path)
                            debug_logger.info(f"Extracted {len(modern_lines)} dialogue lines from file")
                            
                            if not modern_lines:
                                status_message.error("No dialogue lines found in file")
                                debug_logger.error("No dialogue lines found in file")
                                st.session_state.translation_active = False
                                st.stop()
                            
                            # Extract act/scene from filename
                            act, scene = extract_act_scene_from_filename(temp_path)
                            
                            # Translate lines with cancellation support
                            translated_lines = []
                            for i, line in enumerate(modern_lines):
                                # Check for cancellation request
                                if st.session_state.cancel_requested:
                                    status_message.warning(f"Translation cancelled by user after {i} lines")
                                    debug_logger.info(f"Translation cancelled by user after {i} lines")
                                    break
                                
                                # Update progress
                                progress = min(30 + int(60 * (i / len(modern_lines))), 90)
                                progress_bar.progress(progress)
                                status_message.info(f"Translating line {i+1} of {len(modern_lines)}...")
                                
                                # Translate the line
                                try:
                                    result = ui_translator.translate_line(line, use_hybrid_search=True)
                                    if result:
                                        translated_lines.append(result)
                                        debug_logger.info(f"Translated line {i+1}: success")
                                    else:
                                        debug_logger.warning(f"Failed to translate line {i+1}")
                                except Exception as line_error:
                                    debug_logger.error(f"Error translating line {i+1}: {line_error}")
                            
                            # If we have any translated lines, save them
                            if translated_lines:
                                debug_logger.info(f"Saving {len(translated_lines)} translated lines")
                                status_message.info("Saving translation results...")
                                progress_bar.progress(95)
                                
                                # Initialize SceneSaver and save results
                                saver = SceneSaver(translation_id=st.session_state.translation_id, base_output_dir=output_dir)
                                saver.save_scene(
                                    act=act,
                                    scene=scene,
                                    translated_lines=translated_lines,
                                    original_lines=modern_lines[:len(translated_lines)]  # Match lengths
                                )
                                
                                # Update scene info
                                update_scene_info(
                                    translation_id=st.session_state.translation_id,
                                    act=act,
                                    scene=scene,
                                    filename=os.path.basename(temp_path),
                                    line_count=len(translated_lines)
                                )
                                
                                progress_bar.progress(100)
                                
                                if st.session_state.cancel_requested:
                                    status_message.warning(f"Translation cancelled after completing {len(translated_lines)} of {len(modern_lines)} lines")
                                    debug_logger.info(f"Partial translation saved: {len(translated_lines)} of {len(modern_lines)} lines")
                                else:
                                    status_message.success(f"Translation complete! Translated {len(translated_lines)} lines.")
                                
                                st.success(f"Translation saved to: {output_dir}")
                                
                                # Display preview
                                try:
                                    scene_id = f"act_{act.lower()}_scene_{scene.lower()}"
                                    md_path = os.path.join(output_dir, f"{scene_id}.md")
                                    
                                    if os.path.exists(md_path):
                                        with open(md_path, 'r', encoding='utf-8') as f:
                                            md_content = f.read()
                                        st.markdown("### Translation Preview (First 500 characters)")
                                        st.text_area("Preview", md_content[:500] + "...", height=200)
                                        
                                        # Add download button
                                        with open(md_path, "r", encoding="utf-8") as f:
                                            st.download_button(
                                                label="Download Translation",
                                                data=f.read(),
                                                file_name=f"shakespeare_translation_{scene_id}.md",
                                                mime="text/markdown"
                                            )
                                except Exception as preview_error:
                                    debug_logger.error(f"Error displaying preview: {preview_error}")
                            else:
                                status_message.error("No lines were successfully translated")
                                debug_logger.error("No lines were successfully translated")
                        
                        except Exception as e:
                            st.error(f"Error translating play: {e}")
                            import traceback
                            debug_logger.error(f"Exception during translation: {e}")
                            debug_logger.error(f"Stack trace: {traceback.format_exc()}")
                        
                        finally:
                            # Reset translation state
                            st.session_state.translation_active = False
                            st.session_state.cancel_requested = False
                            
                            # Clean up temp file
                            try:
                                if 'temp_path' in locals() and os.path.exists(temp_path):
                                    os.remove(temp_path)
                                    debug_logger.info(f"Removed temporary file: {temp_path}")
                            except Exception as cleanup_error:
                                debug_logger.error(f"Error cleaning up temporary file: {cleanup_error}")
        
        if translation_mode == "Full Scene":
            st.subheader("Full Scene Translation")
            
            # File uploader for scene script
            uploaded_file = st.file_uploader("Upload Scene Script (Markdown)", type="md")
            
            if uploaded_file:
                st.success(f"Uploaded: {uploaded_file.name}")
                
                # Act and scene selection
                col1, col2 = st.columns(2)
                with col1:
                    act = st.text_input("Act Number", "I")
                with col2:
                    scene = st.text_input("Scene Number", "1")
                
                # Output directory
                output_dir = st.text_input("Output Directory", "outputs/translated_scenes")
                
                # Make sure we have a ui_translator in the session
                if "ui_translator" not in st.session_state:
                    st.error("Translator not initialized. Please refresh the page and try again.")
                elif st.button("Start Translation"):
                    # Get the logger for detailed logging
                    debug_logger = CustomLogger("Scene_Translation", log_level="DEBUG", 
                                            log_file=f"logs/scene_translation_{st.session_state.translation_id}.log")
                    debug_logger.info(f"Starting scene translation for Act {act}, Scene {scene}")
                    
                    with st.spinner("Translating scene... This may take several minutes."):
                        try:
                            # Save uploaded file temporarily
                            temp_dir = "temp_uploads"
                            os.makedirs(temp_dir, exist_ok=True)
                            temp_path = os.path.join(temp_dir, uploaded_file.name)
                            
                            with open(temp_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            
                            debug_logger.info(f"Saved uploaded file to temporary location: {temp_path}")
                            debug_logger.info(f"File size: {os.path.getsize(temp_path)} bytes")
                            
                            # Use the ui_translator from the session state
                            ui_translator = st.session_state.ui_translator
                            
                            # Make sure translator is initialized
                            if not ui_translator.is_initialized:
                                debug_logger.warning("Translator not initialized. Attempting to initialize...")
                                success = ui_translator.initialize()
                                if not success:
                                    st.error("Failed to initialize translator. Please try again.")
                                    debug_logger.error("Failed to initialize translator")
                                    st.stop()
                            
                            # Log the state of the translator before translation
                            debug_logger.info(f"Translator state: initialized={ui_translator.is_initialized}, " +
                                            f"translation_id={ui_translator.translation_id}")
                            
                            # Create a progress bar for visual feedback
                            progress_bar = st.progress(0)
                            status_message = st.empty()
                            
                            # Update status message to show activity
                            status_message.info("Reading and parsing scene file...")
                            progress_bar.progress(10)
                            
                            # Translate the file
                            debug_logger.info("Calling translate_file method")
                            
                            # Log start time for performance tracking
                            start_time = time.time()
                            
                            success, result_dir, line_count = ui_translator.translate_file(
                                filepath=temp_path,
                                output_dir=output_dir,
                                force_retranslate=True,  # Force retranslation for testing
                                use_hybrid_search=True
                            )
                            
                            # Log completion time
                            elapsed_time = time.time() - start_time
                            debug_logger.info(f"Translation completed in {elapsed_time:.2f} seconds")
                            
                            # Update UI based on result
                            if success:
                                progress_bar.progress(100)
                                status_message.success(f"Translation complete! Translated {line_count} lines.")
                                st.success(f"Translation saved to: {result_dir}")
                                
                                # Try to read and display part of the translation
                                try:
                                    scene_id = f"act_{act.lower()}_scene_{scene.lower()}"
                                    json_path = os.path.join(result_dir, f"{scene_id}.json")
                                    md_path = os.path.join(result_dir, f"{scene_id}.md")
                                    
                                    if os.path.exists(md_path):
                                        with open(md_path, 'r', encoding='utf-8') as f:
                                            md_content = f.read()
                                        st.markdown("### Translation Preview (Markdown)")
                                        st.text_area("Preview", md_content[:500] + "...", height=200)
                                except Exception as preview_error:
                                    debug_logger.error(f"Error displaying preview: {preview_error}")
                            else:
                                progress_bar.progress(0)
                                status_message.error("Translation failed")
                                st.error(f"Error translating scene: {result_dir}")
                                debug_logger.error(f"Translation failed. Error message: {result_dir}")
                        
                        except Exception as e:
                            st.error(f"Error translating scene: {e}")
                            import traceback
                            debug_logger.error(f"Exception during translation: {e}")
                            debug_logger.error(f"Stack trace: {traceback.format_exc()}")
                        
                        finally:
                            # Clean up temp file
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                                debug_logger.info(f"Removed temporary file: {temp_path}")

        elif translation_mode == "Full Scene":
            st.subheader("Full Scene Translation")
            
            # File uploader for scene script
            uploaded_file = st.file_uploader("Upload Scene Script (Markdown)", type="md")
            
            if uploaded_file:
                st.success(f"Uploaded: {uploaded_file.name}")
                
                # Act and scene selection
                col1, col2 = st.columns(2)
                with col1:
                    act = st.text_input("Act Number", "I")
                with col2:
                    scene = st.text_input("Scene Number", "1")
                
                # Output directory
                output_dir = st.text_input("Output Directory", "outputs/translated_scenes")
                
                # Make sure we have a ui_translator in the session
                if "ui_translator" not in st.session_state:
                    st.error("Translator not initialized. Please refresh the page and try again.")
                # Check if translation is already active
                elif st.session_state.translation_active:
                    # Display progress information
                    st.info("Translation is in progress...")
                    
                    # Display cancel button
                    if st.button("Cancel Translation"):
                        st.session_state.cancel_requested = True
                        st.warning("Cancel requested. Translation will stop after current line completes...")
                elif st.button("Start Translation"):
                    # Reset cancellation flag
                    st.session_state.cancel_requested = False
                    # Set active flag
                    st.session_state.translation_active = True
                    
                    # Get the logger for detailed logging
                    debug_logger = CustomLogger("Scene_Translation", log_level="DEBUG", 
                                            log_file=f"logs/scene_translation_{st.session_state.translation_id}.log")
                    debug_logger.info(f"Starting scene translation for Act {act}, Scene {scene}")
                    
                    with st.spinner("Translating scene... This may take several minutes."):
                        try:
                            # Save uploaded file temporarily
                            temp_dir = "temp_uploads"
                            os.makedirs(temp_dir, exist_ok=True)
                            temp_path = os.path.join(temp_dir, uploaded_file.name)
                            
                            with open(temp_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            
                            debug_logger.info(f"Saved uploaded file to temporary location: {temp_path}")
                            debug_logger.info(f"File size: {os.path.getsize(temp_path)} bytes")
                            
                            # Use the ui_translator from the session state
                            ui_translator = st.session_state.ui_translator
                            
                            # Create containers for progress display
                            progress_bar = st.progress(0)
                            status_message = st.empty()
                            cancel_button_container = st.empty()
                            
                            # Add a cancel button inside the processing loop
                            if cancel_button_container.button("Stop Translation", key="cancel_scene_process"):
                                st.session_state.cancel_requested = True
                                status_message.warning("Cancellation requested. Finishing current processing...")
                            
                            status_message.info("Reading and parsing scene file...")
                            progress_bar.progress(10)
                            
                            # Check for cancellation
                            if st.session_state.cancel_requested:
                                status_message.warning("Translation cancelled by user")
                                debug_logger.info("Translation cancelled by user")
                                st.session_state.translation_active = False
                                st.session_state.cancel_requested = False
                                st.rerun()
                            
                            # Make sure translator is initialized
                            if not ui_translator.is_initialized:
                                debug_logger.warning("Translator not initialized. Attempting to initialize...")
                                success = ui_translator.initialize()
                                if not success:
                                    st.error("Failed to initialize translator. Please try again.")
                                    debug_logger.error("Failed to initialize translator")
                                    st.session_state.translation_active = False
                                    st.stop()
                            
                            # Log the state of the translator before translation
                            debug_logger.info(f"Translator state: initialized={ui_translator.is_initialized}, " +
                                            f"translation_id={ui_translator.translation_id}")
                            
                            # Parse the file to get dialogue lines
                            modern_lines = parse_markdown_scene(temp_path)
                            debug_logger.info(f"Extracted {len(modern_lines)} dialogue lines from file")
                            
                            if not modern_lines:
                                status_message.error("No dialogue lines found in file")
                                debug_logger.error("No dialogue lines found in file")
                                st.session_state.translation_active = False
                                st.stop()
                            
                            # Update status message
                            status_message.info("Starting translation... (Click 'Stop Translation' to cancel)")
                            progress_bar.progress(20)
                            
                            # Check for cancellation again
                            if st.session_state.cancel_requested:
                                status_message.warning("Translation cancelled by user")
                                debug_logger.info("Translation cancelled by user")
                                st.session_state.translation_active = False
                                st.session_state.cancel_requested = False
                                st.rerun()
                            
                            # Translate lines with cancellation support
                            translated_lines = []
                            for i, line in enumerate(modern_lines):
                                # Check for cancellation request
                                if st.session_state.cancel_requested:
                                    status_message.warning(f"Translation cancelled by user after {i} lines")
                                    debug_logger.info(f"Translation cancelled by user after {i} lines")
                                    break
                                
                                # Update progress
                                progress = min(30 + int(60 * (i / len(modern_lines))), 90)
                                progress_bar.progress(progress)
                                status_message.info(f"Translating line {i+1} of {len(modern_lines)}...")
                                
                                # Translate the line
                                try:
                                    result = ui_translator.translate_line(line, use_hybrid_search=True)
                                    if result:
                                        translated_lines.append(result)
                                        debug_logger.info(f"Translated line {i+1}: success")
                                    else:
                                        debug_logger.warning(f"Failed to translate line {i+1}")
                                except Exception as line_error:
                                    debug_logger.error(f"Error translating line {i+1}: {line_error}")
                            
                            # If we have any translated lines, save them
                            if translated_lines:
                                debug_logger.info(f"Saving {len(translated_lines)} translated lines")
                                status_message.info("Saving translation results...")
                                progress_bar.progress(95)
                                
                                # Initialize SceneSaver and save results
                                saver = SceneSaver(translation_id=st.session_state.translation_id, base_output_dir=output_dir)
                                saver.save_scene(
                                    act=act,
                                    scene=scene,
                                    translated_lines=translated_lines,
                                    original_lines=modern_lines[:len(translated_lines)]  # Match lengths
                                )
                                
                                # Update scene info
                                update_scene_info(
                                    translation_id=st.session_state.translation_id,
                                    act=act,
                                    scene=scene,
                                    filename=os.path.basename(temp_path),
                                    line_count=len(translated_lines)
                                )
                                
                                progress_bar.progress(100)
                                
                                if st.session_state.cancel_requested:
                                    status_message.warning(f"Translation cancelled after completing {len(translated_lines)} of {len(modern_lines)} lines")
                                    debug_logger.info(f"Partial translation saved: {len(translated_lines)} of {len(modern_lines)} lines")
                                else:
                                    status_message.success(f"Translation complete! Translated {len(translated_lines)} lines.")
                                
                                st.success(f"Translation saved to: {output_dir}")
                                
                                # Display preview
                                try:
                                    scene_id = f"act_{act.lower()}_scene_{scene.lower()}"
                                    md_path = os.path.join(output_dir, f"{scene_id}.md")
                                    
                                    if os.path.exists(md_path):
                                        with open(md_path, 'r', encoding='utf-8') as f:
                                            md_content = f.read()
                                        st.markdown("### Translation Preview (First 500 characters)")
                                        st.text_area("Preview", md_content[:500] + "...", height=200)
                                        
                                        # Add download button
                                        with open(md_path, "r", encoding="utf-8") as f:
                                            st.download_button(
                                                label="Download Translation",
                                                data=f.read(),
                                                file_name=f"shakespeare_translation_{scene_id}.md",
                                                mime="text/markdown"
                                            )
                                except Exception as preview_error:
                                    debug_logger.error(f"Error displaying preview: {preview_error}")
                            else:
                                status_message.error("No lines were successfully translated")
                                debug_logger.error("No lines were successfully translated")
                        
                        except Exception as e:
                            st.error(f"Error translating scene: {e}")
                            import traceback
                            debug_logger.error(f"Exception during translation: {e}")
                            debug_logger.error(f"Stack trace: {traceback.format_exc()}")
                        
                        finally:
                            # Reset translation state
                            st.session_state.translation_active = False
                            st.session_state.cancel_requested = False
                            
                            # Clean up temp file
                            try:
                                if 'temp_path' in locals() and os.path.exists(temp_path):
                                    os.remove(temp_path)
                                    debug_logger.info(f"Removed temporary file: {temp_path}")
                            except Exception as cleanup_error:
                                debug_logger.error(f"Error cleaning up temporary file: {cleanup_error}")

        elif translation_mode == "Section":
            st.subheader("Section Translation")
            
            # Initialize translation manager
            if "translation_manager" not in st.session_state:
                try:
                    # Initialize translation manager with the selected ID
                    st.session_state.translation_manager = TranslationManager()
                    st.session_state.translation_manager.start_translation_session(st.session_state.translation_id)
                except Exception as e:
                    st.error(f"Error initializing translation manager: {e}")
            
            # Text area for input lines
            if not st.session_state.modern_lines:
                modern_text = st.text_area(
                    "Enter modern text (one or more lines)",
                    height=150
                )
                
                if st.button("Prepare Translation"):
                    if modern_text:
                        # Split text into lines
                        st.session_state.modern_lines = [line.strip() for line in modern_text.split('\n') if line.strip()]
                        
                        if not st.session_state.modern_lines:
                            st.warning("No valid lines found in input text.")
                        else:
                            st.success(f"Ready to translate {len(st.session_state.modern_lines)} lines.")
                    else:
                        st.warning("Please enter some text to translate.")
            
            # If we have lines to translate, show the translation interface
            if st.session_state.modern_lines:
                # Display the current line
                current_idx = st.session_state.current_line_index
                if 0 <= current_idx < len(st.session_state.modern_lines):
                    current_line = st.session_state.modern_lines[current_idx]
                    
                    st.markdown(f"**Line {current_idx + 1} of {len(st.session_state.modern_lines)}**")
                    st.markdown(f"**Modern Text:**")
                    st.markdown(f"> {current_line}")
                    
                    # Show the translated line if available
                    if current_idx < len(st.session_state.translated_lines):
                        translated = st.session_state.translated_lines[current_idx]
                        
                        st.markdown(f"**Shakespearean Translation:**")
                        st.markdown(f"> {translated['text']}")
                        
                        # Show references
                        st.markdown("**References:**")
                        for ref in translated.get('references', []):
                            st.markdown(f"- {ref.get('title', 'Unknown')} ({ref.get('act', '')}.{ref.get('scene', '')}.{ref.get('line', '')})")
                        
                        # Navigation buttons
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("Previous Line") and current_idx > 0:
                                st.session_state.current_line_index -= 1
                                st.rerun()
                        
                        with col2:
                            if st.button("Rerun Translation"):
                                with st.spinner("Retranslating..."):
                                    try:
                                        # Call the translation manager to translate the line
                                        translated = st.session_state.translation_manager.translate_line(
                                            current_line, {}, use_hybrid_search=use_hybrid_search)
                                        
                                        if translated:
                                            # Update the translated line
                                            st.session_state.translated_lines[current_idx] = translated
                                            st.success("Retranslation successful!")
                                            st.rerun()
                                        else:
                                            st.error("Translation failed. Please try again.")
                                    except Exception as e:
                                        st.error(f"Error in translation: {e}")
                                        logger.error(f"Error translating line: {e}")
                        
                        with col3:
                            if st.button("Next Line") and current_idx < len(st.session_state.modern_lines) - 1:
                                st.session_state.current_line_index += 1
                                
                                # If we don't have a translation for the next line yet, generate one
                                if st.session_state.current_line_index >= len(st.session_state.translated_lines):
                                    st.rerun()  # This will trigger the else clause below
                                else:
                                    st.rerun()
                    
                    else:
                        # No translation yet, translate the current line
                        with st.spinner("Translating..."):
                            try:
                                # Call the translation manager to translate the line
                                translated = st.session_state.translation_manager.translate_line(
                                    current_line, {}, use_hybrid_search=use_hybrid_search)
                                
                                if translated:
                                    # Add the translated line
                                    st.session_state.translated_lines.append(translated)
                                    st.success("Translation successful!")
                                    st.rerun()
                                else:
                                    st.error("Translation failed. Please try again.")
                            except Exception as e:
                                st.error(f"Error in translation: {e}")
                                logger.error(f"Error translating line: {e}")
                
                # Save all translated lines button
                if st.session_state.translated_lines:
                    if st.button("Save All Translated Lines"):
                        try:
                            # Initialize SceneSaver
                            saver = SceneSaver(base_output_dir="outputs/section_translations")
                            
                            # Save the translated lines
                            saver.save_scene(
                                act="Custom",
                                scene="Section",
                                translated_lines=st.session_state.translated_lines,
                                original_lines=st.session_state.modern_lines
                            )
                            
                            st.success("Saved all translated lines!")
                            
                            # Provide download link
                            output_path = "outputs/section_translations/act_custom_scene_section.md"
                            if os.path.exists(output_path):
                                with open(output_path, "r") as f:
                                    file_content = f.read()
                                
                                st.download_button(
                                    label="Download Translation",
                                    data=file_content,
                                    file_name="shakespeare_translation.md",
                                    mime="text/markdown"
                                )
                            
                        except Exception as e:
                            st.error(f"Error saving translations: {e}")
                            logger.error(f"Error saving translations: {e}")
                
                # Reset button
                if st.button("Reset Translation Session"):
                    st.session_state.modern_lines = []
                    st.session_state.translated_lines = []
                    st.session_state.current_line_index = 0
                    st.success("Translation session reset.")
                    st.rerun()

# Footer
st.divider()
st.markdown("Shakespeare AI - Developed with ❤️ and 📚")