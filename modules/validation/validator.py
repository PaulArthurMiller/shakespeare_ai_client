# modules/validation/validator.py

import os
import json
import re
import unicodedata
from typing import Dict, Any, List, Tuple
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

class Validator:
    def __init__(self, ground_truth_path: str = "data/line_corpus/lines.json"):
        self.logger = CustomLogger("Validator")
        self.logger.info("Initializing Validator")
        self.ground_truth_path = ground_truth_path
        self.ground_truth = self._load_ground_truth()

    def _load_ground_truth(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.ground_truth_path):
            self.logger.error(f"Ground truth file not found: {self.ground_truth_path}")
            raise FileNotFoundError(f"Missing ground truth file at {self.ground_truth_path}")
        try:
            with open(self.ground_truth_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.info(f"Loaded {len(data['chunks'])} ground truth lines")
            return data["chunks"]
        except Exception as e:
            self.logger.critical(f"Error loading ground truth: {e}")
            return []

    def _tokenize_line_for_validation(self, line_text: str) -> List[Tuple[str, int]]:
        """
        Tokenizes a line of text using the same logic as line_chunker.py to create word indices.
        Returns a list of tuples (word, index) for each word in the line.
        """
        self.logger.debug(f"Tokenizing line: '{line_text}'")
        
        # This part exactly mimics the behavior in line_chunker.py
        if not SPACY_AVAILABLE:
            # Fallback tokenization logic if spaCy is not available
            words = re.findall(r"\b\w[\w']*\b", line_text)
            self.logger.warning("Using fallback tokenization - spaCy not available")
            return [(word, i) for i, word in enumerate(words)]
        
        try:
            # Normalize quotes first, just like in line_chunker.py
            line_text = self._normalize_quotes(line_text)
            
            doc = nlp(line_text)
            # Filter out punctuation and whitespace, exactly like line_chunker does
            tokens = [(token.text, i) for i, token in enumerate([token for token in doc 
                    if not token.is_punct and not token.is_space])]
            
            self.logger.debug(f"Identified {len(tokens)} tokens in line")
            for i, (token, idx) in enumerate(tokens):
                self.logger.debug(f"  Token {idx}: '{token}'")
            
            return tokens
        except Exception as e:
            self.logger.error(f"spaCy error: {e}")
            # Fallback to simple tokenization, same as line_chunker.py
            words = re.findall(r"\b\w[\w']*\b", line_text)
            return [(word, i) for i, word in enumerate(words)]

    def _normalize_quotes(self, line: str) -> str:
        """Replace curly quotes/apostrophes with plain ASCII, exactly like in line_chunker.py."""
        replacements = {
            "\u2018": "'",
            "\u2019": "'",
            "\u201C": '"',
            "\u201D": '"',
        }
        for old, new in replacements.items():
            line = line.replace(old, new)
        return line

    def _normalize_and_clean(self, text: str) -> str:
        """Normalize text for comparison by standardizing whitespace and lowercasing."""
        # First normalize quotes like in line_chunker.py
        text = self._normalize_quotes(text)
        # Then clean whitespace and lowercase
        return re.sub(r'\s+', ' ', text.lower()).strip()

    def validate_line(self, assembled_text: str, references: List[Dict[str, Any]]) -> bool:
        """
        Validates if assembled text exactly matches the fragments from ground truth references
        using word indices to extract the exact fragments, maintaining the exact order provided.
        """
        self.logger.debug(f"Validating assembled line: '{assembled_text}'")
        
        extracted_fragments_gt = []
        reference_details = []
        
        for ref in references:
            # Log the reference metadata
            ref_str = ", ".join([f"{k}: {v}" for k, v in ref.items() if k not in ["POS", "mood"]])
            self.logger.debug(f"Processing reference: {ref_str}")
            
            # Extract required metadata
            title = ref.get("title", "")
            act = ref.get("act", "")  # Could be null/None in the data
            scene = ref.get("scene", "")  # Could be null/None in the data
            line_num = ref.get("line", "")
            word_index = ref.get("word_index", "")
            
            # We still need some identifiers to find an entry
            if not title or not str(line_num):
                self.logger.warning(f"Incomplete essential reference metadata (title or line): {ref}")
                continue
            
            # Find the ground truth entry - modified to handle null/None act/scene
            gt_entry = None
            for entry in self.ground_truth:
                # Handle null act/scene more explicitly
                act_match = False
                scene_match = False
                
                # Check for null/None values or matching values
                if (act is None or act == "" or act == "null") and (entry.get("act") is None or entry.get("act") == "" or entry.get("act") == "null"):
                    act_match = True
                elif str(entry.get("act")) == str(act):  # Convert both to string for comparison
                    act_match = True
                    
                if (scene is None or scene == "" or scene == "null") and (entry.get("scene") is None or entry.get("scene") == "" or entry.get("scene") == "null"):
                    scene_match = True
                elif str(entry.get("scene")) == str(scene):  # Convert both to string for comparison
                    scene_match = True
                
                if (entry.get("title") == title and 
                    act_match and 
                    scene_match and 
                    str(entry.get("line")) == str(line_num)):
                    gt_entry = entry
                    break
            
            if not gt_entry:
                self.logger.warning(f"No ground truth entry found for {title}, Act {act}, Scene {scene}, Line {line_num}")
                continue
            
            gt_text = gt_entry.get("text", "")
            self.logger.debug(f"Found reference in ground truth: '{gt_text}'")
            
            # Use word_index to extract the fragment
            if word_index:
                try:
                    # Tokenize the ground truth line using the exact same logic as line_chunker.py
                    tokenized_line = self._tokenize_line_for_validation(gt_text)
                    
                    # Parse the word_index
                    if "," in word_index:
                        start, end = map(int, word_index.split(","))
                    else:
                        self.logger.warning(f"Invalid word_index format: {word_index}")
                        continue
                    
                    # Extract words within the range
                    fragment_words = []
                    for word, idx in tokenized_line:
                        if start <= idx <= end:
                            fragment_words.append(word)
                    
                    if fragment_words:
                        fragment_gt = " ".join(fragment_words)
                        extracted_fragments_gt.append(fragment_gt)
                        reference_details.append({
                            "title": title,
                            "act": act,
                            "scene": scene,
                            "line": line_num,
                            "word_index": word_index,
                            "fragment": fragment_gt,
                            "tokenized": tokenized_line
                        })
                        self.logger.debug(f"Extracted fragment: '{fragment_gt}' from indices {start}-{end}")
                    else:
                        self.logger.warning(f"No words found in range {start}-{end} for: '{gt_text}'")
                        self.logger.debug(f"Tokenized line: {tokenized_line}")
                except Exception as e:
                    self.logger.error(f"Error extracting fragment with word_index {word_index}: {e}")
            else:
                self.logger.warning(f"SERIOUS ISSUE: No word_index provided for reference: {ref}")
                # Still try to use the full line for validation, but flag the issue
                extracted_fragments_gt.append(gt_text)
                reference_details.append({
                    "title": title,
                    "act": act,
                    "scene": scene,
                    "line": line_num,
                    "fragment": gt_text,
                    "MISSING_WORD_INDEX": True
                })
        
        if not extracted_fragments_gt:
            self.logger.warning("No fragments extracted from ground truth references")
            return False
        
        # Log reference summary
        self.logger.debug(f"Reference summary:")
        for i, ref_detail in enumerate(reference_details):
            self.logger.debug(f"  [{i+1}] {ref_detail['title']}, Act {ref_detail['act']}, Scene {ref_detail['scene']}, Line {ref_detail['line']}")
            self.logger.debug(f"      Fragment: '{ref_detail['fragment']}'")
            if "tokenized" in ref_detail:
                token_str = ", ".join([f"'{word}':{idx}" for word, idx in ref_detail["tokenized"]])
                self.logger.debug(f"      Tokenized: [{token_str}]")
            if ref_detail.get("MISSING_WORD_INDEX", False):
                self.logger.warning(f"      MISSING WORD INDEX FOR THIS REFERENCE!")
        
        # Normalize fragments and assembled text using our _normalize_quotes first
        normalized_fragments_gt = [self._normalize_and_clean(frag) for frag in extracted_fragments_gt]
        normalized_assembled = self._normalize_and_clean(assembled_text)
        
        # For aggressive comparison, remove all spaces and punctuation
        alpha_only_fragments_gt = ["".join(c for c in frag if c.isalnum()) for frag in normalized_fragments_gt]
        alpha_only_assembled = "".join(c for c in normalized_assembled if c.isalnum())
        
        # Combine the fragments in the exact order provided by references
        expected_text_gt = " ".join(normalized_fragments_gt)
        expected_alpha_only_gt = "".join(alpha_only_fragments_gt)
        
        # Log the normalized sources and assembled text
        self.logger.debug(f"Normalized ground truth: '{expected_text_gt}'")
        self.logger.debug(f"Normalized assembled: '{normalized_assembled}'")
        self.logger.debug(f"Alpha-only ground truth: '{expected_alpha_only_gt}'")
        self.logger.debug(f"Alpha-only assembled: '{alpha_only_assembled}'")
        
        # First try normal comparison (with spaces)
        if normalized_assembled == expected_text_gt:
            self.logger.info("Validation passed: Assembled line exactly matches ordered source fragments")
            return True
        else:
            self.logger.warning("Standard normalized text comparison failed")
            self.logger.debug(f"Expected: '{expected_text_gt}'")
            self.logger.debug(f"Got:      '{normalized_assembled}'")
            
            # Try the alpha-only comparison as a fallback
            if alpha_only_assembled == expected_alpha_only_gt:
                self.logger.info("Validation passed: Alpha-only content of assembled line matches source fragments")
                return True
            else:
                self.logger.warning("Alpha-only comparison also failed")
                self.logger.debug(f"Expected (alpha-only): '{expected_alpha_only_gt}'")
                self.logger.debug(f"Got (alpha-only):      '{alpha_only_assembled}'")
                return False
