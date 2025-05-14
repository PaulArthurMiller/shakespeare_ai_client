"""
Line chunker module for Shakespeare AI project.

This version resets the line numbering at each new scene.
We can therefore reference, for example, "line 28 of Act II, Scene II, in Macbeth."
"""

import re
import time
import os
import json
from typing import List, Dict, Any, Tuple, Optional
from .base import ChunkBase
from modules.utils.logger import CustomLogger

try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
        SPACY_AVAILABLE = True
    except OSError:
        SPACY_AVAILABLE = False
except ImportError:
    SPACY_AVAILABLE = False

def _normalize_quotes(line: str) -> str:
    """Replace curly quotes/apostrophes with plain ASCII."""
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201C": '"',
        "\u201D": '"',
    }
    for old, new in replacements.items():
        line = line.replace(old, new)
    return line

class LineChunker(ChunkBase):
    """Chunker for processing Shakespeare's text into full lines,
    resetting line numbering at each new scene (and new play title).
    """
    
    def __init__(self, logger: Optional[CustomLogger] = None):
        super().__init__(chunk_type='line')
        self.logger = logger or CustomLogger("LineChunker")
        self.logger.info("Initializing LineChunker")
        
        if not SPACY_AVAILABLE:
            self.logger.warning("spaCy is not available - using fallback tokenization")
            self.logger.info("To install spaCy: pip install spacy && python -m spacy download en_core_web_sm")
        
        # Updated regex for detecting acts (roman numerals or INDUCTION) and scenes (roman, digits, or PROLOGUE)
        self.act_pattern = re.compile(r'^ACT\s+((?:INDUCTION|[IVX]+))', re.IGNORECASE)
        self.scene_pattern = re.compile(r'^SCENE\s+((?:PROLOGUE|[IVX]+|\d+))', re.IGNORECASE)
        
        # Pattern for single-number lines (for sonnets, if current_title contains "SONNETS")
        self.sonnet_number_pattern = re.compile(r'^(\d+)$')
        
        # All-caps lines
        self.all_caps_pattern = re.compile(r'^[A-Z\s.,;:!?]+$')
        
        # Known Shakespeare titles (use uppercase for matching).
        self.shakespeare_titles = {
            "THE SONNETS",
            "ALL'S WELL THAT ENDS WELL",
            "THE TRAGEDY OF ANTONY AND CLEOPATRA",
            "AS YOU LIKE IT",
            "THE COMEDY OF ERRORS",
            "THE TRAGEDY OF CORIOLANUS",
            "CYMBELINE",
            "THE TRAGEDY OF HAMLET, PRINCE OF DENMARK",
            "THE FIRST PART OF KING HENRY THE FOURTH",
            "THE SECOND PART OF KING HENRY THE FOURTH",
            "THE LIFE OF KING HENRY THE FIFTH",
            "THE FIRST PART OF HENRY THE SIXTH",
            "THE SECOND PART OF KING HENRY THE SIXTH",
            "THE THIRD PART OF KING HENRY THE SIXTH",
            "KING HENRY THE EIGHTH",
            "THE LIFE AND DEATH OF KING JOHN",
            "THE TRAGEDY OF JULIUS CAESAR",
            "THE TRAGEDY OF KING LEAR",
            "LOVE'S LABOUR'S LOST",
            "THE TRAGEDY OF MACBETH",
            "MEASURE FOR MEASURE",
            "THE MERCHANT OF VENICE",
            "THE MERRY WIVES OF WINDSOR",
            "A MIDSUMMER NIGHT'S DREAM",
            "MUCH ADO ABOUT NOTHING",
            "THE TRAGEDY OF OTHELLO, THE MOOR OF VENICE",
            "PERICLES, PRINCE OF TYRE",
            "KING RICHARD THE SECOND",
            "KING RICHARD THE THIRD",
            "THE TRAGEDY OF ROMEO AND JULIET",
            "THE TAMING OF THE SHREW",
            "THE TEMPEST",
            "THE LIFE OF TIMON OF ATHENS",
            "THE TRAGEDY OF TITUS ANDRONICUS",
            "TROILUS AND CRESSIDA",
            "TWELFTH NIGHT; OR, WHAT YOU WILL",
            "THE TWO GENTLEMEN OF VERONA",
            "THE TWO NOBLE KINSMEN",
            "A WINTER'S TALE",
            "A LOVER'S COMPLAINT",
            "THE PASSIONATE PILGRIM",
            "THE PHOENIX AND THE TURTLE",
            "THE RAPE OF LUCRECE",
            "VENUS AND ADONIS"
        }
        
        # Track detected titles, acts, and scenes for validation
        self.titles_detected = set()
        self.acts_by_title = {}
        self.scenes_by_title_and_act = {}
        
        self.logger.debug("Compiled regular expressions for text parsing")
    
    def _count_syllables(self, word: str) -> int:
        # Skip if it's punctuation or doesn't contain at least one letter
        if not any(c.isalpha() for c in word):
            return 0

        word = word.lower()
        if len(word) <= 3:
            return 1
        if word.endswith('e'):
            word = word[:-1]
        vowels = re.findall(r'[aeiouy]+', word)
        return max(1, len(vowels))
    
    def _process_line_with_spacy(self, line: str) -> Tuple[List[str], List[str], int]:
        """Use spaCy for tokenization/POS, excluding punctuation and whitespace."""
        if not SPACY_AVAILABLE:
            words = re.findall(r"\b\w[\w']*\b", line)
            pos_tags = [""] * len(words)
            return words, pos_tags, len(words)
        
        try:
            doc = nlp(line)
            words = [token.text for token in doc if not token.is_punct and not token.is_space]
            pos_tags = [token.pos_ for token in doc if not token.is_punct and not token.is_space]
            return words, pos_tags, len(words)
        except Exception as e:
            self.logger.error(f"spaCy error: {e}")
            words = re.findall(r"\b\w[\w']*\b", line)
            pos_tags = [""] * len(words)
            return words, pos_tags, len(words)
    
    def _is_structural_line(self, line: str) -> bool:
        """Check if line is an act/scene line or all-caps structural text."""
        if self.act_pattern.match(line):
            return True
        if self.scene_pattern.match(line):
            return True
        if self.all_caps_pattern.match(line):
            return True
        return False
    
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        start_time = time.time()
        self.logger.info("Starting text chunking process")
        self.logger.debug(f"Input text length: {len(text)} chars")
        
        lines = text.split('\n')
        self.logger.debug(f"Split text into {len(lines)} raw lines")
        
        current_title = "Unknown"
        current_act = None
        current_scene = None
        
        # We'll keep a global chunk ID counter, so each chunk is unique
        chunk_counter = 0
        
        # We'll keep a separate line index that resets each time we detect a new scene or new title
        scene_line_index = 0
        
        chunks = []
        
        # Reset tracking dictionaries for validation
        self.titles_detected = set()
        self.acts_by_title = {}
        self.scenes_by_title_and_act = {}
        
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            
            # Normalize quotes
            line = _normalize_quotes(line)
            
            # Check if line matches a known Shakespeare title (in uppercase)
            if line.upper() in self.shakespeare_titles:
                current_title = line
                self.logger.info(f"Detected title: {current_title}")
                # Track titles for validation
                self.titles_detected.add(current_title)
                self.acts_by_title[current_title] = set()
                self.scenes_by_title_and_act[current_title] = {}
                
                # Reset act/scene/line numbering for a new play
                current_act = None
                current_scene = None
                scene_line_index = 0
                # Skip creating a chunk for the title line
                continue
            
            # Check for ACT
            act_match = self.act_pattern.match(line)
            if act_match:
                current_act = act_match.group(1).upper()
                current_scene = None
                scene_line_index = 0
                self.logger.info(f"Detected Act {current_act} for title '{current_title}'")
                
                # Track acts for validation
                if current_title in self.acts_by_title:
                    self.acts_by_title[current_title].add(current_act)
                    if current_act not in self.scenes_by_title_and_act[current_title]:
                        self.scenes_by_title_and_act[current_title][current_act] = set()
                
                continue
            
            # Check for SCENE
            scene_match = self.scene_pattern.match(line)
            if scene_match:
                current_scene = scene_match.group(1).upper()  # could be "PROLOGUE" or digits
                scene_line_index = 0  # reset line numbering for new scene
                self.logger.info(f"Detected Scene {current_scene} in Act {current_act}, title '{current_title}'")
                
                # Track scenes for validation
                if (current_title in self.scenes_by_title_and_act and 
                    current_act in self.scenes_by_title_and_act[current_title]):
                    self.scenes_by_title_and_act[current_title][current_act].add(current_scene)
                
                continue
            
            # Check for sonnet numbers if this is THE SONNETS
            if "SONNETS" in current_title.upper():
                sonnet_match = self.sonnet_number_pattern.match(line)
                if sonnet_match:
                    current_act = sonnet_match.group(1)
                    current_scene = ""
                    scene_line_index = 0
                    self.logger.info(f"Detected Sonnet {current_act}")
                    
                    # Track sonnet numbers as acts for validation
                    if current_title in self.acts_by_title:
                        self.acts_by_title[current_title].add(current_act)
                        if current_act not in self.scenes_by_title_and_act[current_title]:
                            self.scenes_by_title_and_act[current_title][current_act] = set()
                    
                    continue
            
            # If this looks like a structural line (all-caps or something we skip), skip it
            if self._is_structural_line(line):
                self.logger.debug(f"Skipping structural line: {line}")
                continue
            
            # Now it's a regular spoken (or textual) line. Increment counters.
            chunk_counter += 1
            scene_line_index += 1
            
            words, pos_tags, word_count = self._process_line_with_spacy(line)
            total_syllables = sum(self._count_syllables(w) for w in words)
            
            chunk = {
                "chunk_id": f"chunk_{chunk_counter}",
                "title": current_title,
                # This 'line' is the line number within the current scene
                "line": scene_line_index,  
                "act": current_act,
                "scene": current_scene,
                "text": line,
                "word_index": f"0,{word_count - 1}",
                "syllables": total_syllables,
                "POS": pos_tags,
                "mood": "neutral",
                "word_count": word_count
            }
            
            # Log warning for incomplete metadata
            if current_act is None or current_scene is None:
                self.logger.warning(
                    f"⚠️ Line with incomplete metadata: title='{current_title}', "
                    f"act={current_act}, scene={current_scene}, line={scene_line_index}: {line[:50]}..."
                )
            
            chunks.append(chunk)
            self.logger.debug(
                f"Created chunk_{chunk_counter} for title='{current_title}', "
                f"Act={current_act}, Scene={current_scene}, line_in_scene={scene_line_index}"
            )
        
        self.chunks = chunks
        elapsed = time.time() - start_time
        self.logger.info(f"Completed text chunking: {len(chunks)} chunks in {elapsed:.2f}s")
        
        # Print validation summary of detected titles, acts, and scenes
        self._print_detection_summary()
        
        return chunks
    
    def _print_detection_summary(self) -> None:
        """Print a summary of detected titles, acts, and scenes for validation."""
        self.logger.info("\n=== DETECTION SUMMARY ===")
        self.logger.info(f"Detected {len(self.titles_detected)} titles:")
        
        for title in sorted(self.titles_detected):
            acts = self.acts_by_title.get(title, set())
            self.logger.info(f"\n{title}:")
            self.logger.info(f"  - Acts: {', '.join(sorted(acts)) if acts else 'None'}")
            
            for act in sorted(acts):
                scenes = self.scenes_by_title_and_act.get(title, {}).get(act, set())
                self.logger.info(f"    - Act {act} Scenes: {', '.join(sorted(scenes)) if scenes else 'None'}")
    
    def get_lines_by_act_scene(self, act: str, scene: str) -> List[Dict[str, Any]]:
        """Retrieve lines that match a given Act and Scene."""
        if not self.chunks:
            self.logger.warning("No chunks available. Process text first.")
            return []
        
        matches = [
            c for c in self.chunks
            if c.get('act') == act and c.get('scene') == scene
        ]
        self.logger.info(f"Found {len(matches)} lines in Act {act}, Scene {scene}")
        return matches
    
    def get_dialogue_exchange(self, start_index: int, max_lines: int = 10) -> List[Dict[str, Any]]:
        """Return up to `max_lines` consecutive chunks starting from `start_index` in the .chunks list."""
        if not self.chunks:
            self.logger.warning("No chunks available. Process text first.")
            return []
        
        if start_index < 0 or start_index >= len(self.chunks):
            self.logger.warning(
                f"Invalid start_index {start_index} for {len(self.chunks)} total chunks.")
            return []
        
        end_idx = min(start_index + max_lines, len(self.chunks))
        exchange = self.chunks[start_index:end_idx]
        self.logger.info(f"Retrieved {len(exchange)} lines of dialogue exchange.")
        return exchange
    
    def get_sonnet_lines(self, sonnet_number: str) -> List[Dict[str, Any]]:
        """Get lines from a particular sonnet number (act=sonnet_number, scene='')."""
        if not self.chunks:
            self.logger.warning("No chunks available. Process text first.")
            return []
        
        sonnet_lines = [
            c for c in self.chunks
            if c.get('act') == sonnet_number and c.get('scene') == ""
        ]
        self.logger.info(f"Found {len(sonnet_lines)} lines in Sonnet {sonnet_number}")
        return sonnet_lines

if __name__ == "__main__":
    input_file = "data/processed_texts/complete_shakespeare_ready.txt"
    output_file = "data/processed_chunks/lines.json"
    logger = CustomLogger("LineChunkerMain", log_level="INFO")
    
    try:
        chunker = LineChunker(logger=logger)
        logger.info(f"Reading input file: {input_file}")
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            logger.critical(f"Input file not found: {input_file}")
            exit(1)
        except Exception as e:
            logger.critical(f"Error reading input file: {str(e)}")
            exit(1)
        
        logger.info("Processing text...")
        chunks = chunker.chunk_text(text)
        logger.info(f"Generated {len(chunks)} line chunks.")
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        logger.info(f"Saving chunks to: {output_file}")
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'chunk_type': 'line',
                    'chunks': chunks,
                    'total_chunks': len(chunks)
                }, f, indent=2)
            logger.info("Chunks saved successfully!")
        except Exception as e:
            logger.critical(f"Error saving output file: {str(e)}")
            exit(1)
            
    except Exception as e:
        logger.critical(f"Unexpected error: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        exit(1)