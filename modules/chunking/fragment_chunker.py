"""
Fragment chunker module for Shakespeare AI project.

This module provides functionality to chunk Shakespeare's text into small
fragments (3-8 words) based on semantic groupings, preserving metadata.
"""
import re
from typing import List, Dict, Any, Optional
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


class FragmentChunker(ChunkBase):
    """Chunker for processing Shakespeare's text into semantic word fragments.

    This chunker creates 3-8 word fragments from each line using spaCy's syntactic parsing,
    preserving references to the parent line and avoiding overlap.
    """

    def __init__(self, min_words: int = 3, max_words: int = 8, logger: Optional[CustomLogger] = None):
        super().__init__(chunk_type='fragment')
        self.logger = logger or CustomLogger("FragmentChunker")
        self.logger.info("Initializing FragmentChunker")

        self.min_words = min_words
        self.max_words = max_words
        self.logger.debug(f"Set word limits: min={min_words}, max={max_words}")

        if not SPACY_AVAILABLE:
            self.logger.warning("spaCy is not available - using fallback tokenization")
            self.logger.info("To install spaCy: pip install spacy && python -m spacy download en_core_web_sm")

    def _normalize_quotes(self, line: str) -> str:
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

    def _process_line_with_spacy(self, line: str) -> List[Any]:
        """Process a line with spaCy, excluding punctuation and whitespace."""
        if not SPACY_AVAILABLE:
            words = re.findall(r"\b\w[\w']*\b", line)
            return words
        
        try:
            # Normalize quotes first
            line = self._normalize_quotes(line)
            
            doc = nlp(line)
            # Filter out punctuation and whitespace
            tokens = [token for token in doc if not token.is_punct and not token.is_space]
            return tokens
        except Exception as e:
            self.logger.error(f"spaCy error: {e}")
            words = re.findall(r"\b\w[\w']*\b", line)
            return words

    def chunk_from_line_chunks(self, line_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.logger.info("Starting fragment chunking from line chunks")
        self.logger.debug(f"Processing {len(line_chunks)} line chunks")
        chunks = []

        # Force max_words to 6
        self.max_words = 6

        for line_chunk in line_chunks:
            line_text = line_chunk['text']
            line_id = line_chunk['chunk_id']
            source_chunk_id = line_chunk['chunk_id']  # Store original chunk_id
            
            # Normalize the text
            line_text = self._normalize_quotes(line_text)

            # Process the full line with spaCy
            line_doc = nlp(line_text) if SPACY_AVAILABLE else None
            
            # Get tokens without punctuation and whitespace
            if SPACY_AVAILABLE and line_doc:
                line_tokens = [token for token in line_doc if not token.is_space and not token.is_punct]
                token_words = [token.text for token in line_tokens]
                pos_tags = [token.pos_ for token in line_tokens]
            else:
                # Fallback tokenization
                token_words = re.findall(r"\b\w[\w']*\b", line_text)
                line_tokens = token_words
                pos_tags = [""] * len(token_words)

            used_indices = set()
            fragment_idx = 0

            # --- Primary Strategy: Use spaCy subtrees ---
            if SPACY_AVAILABLE and line_doc:
                for token in line_doc:
                    subtree_tokens = list(token.subtree)
                    word_tokens = [t for t in subtree_tokens if not t.is_space and not t.is_punct]
                    if len(word_tokens) < self.min_words or len(word_tokens) > self.max_words:
                        continue

                    word_texts = [t.text for t in word_tokens]
                    try:
                        for i in range(len(token_words) - len(word_texts) + 1):
                            if token_words[i:i+len(word_texts)] == word_texts:
                                word_index_start = i
                                word_index_end = i + len(word_texts) - 1
                                if any(idx in used_indices for idx in range(word_index_start, word_index_end + 1)):
                                    raise ValueError("Overlapping fragment indices")
                                break
                        else:
                            raise ValueError("Fragment words not aligned")
                    except ValueError:
                        continue

                    fragment_text = " ".join(word_texts).strip()
                    fragment_pos = [t.pos_ for t in word_tokens]
                    total_syllables = sum(self._count_syllables(str(t.text)) for t in word_tokens)

                    self.logger.debug(f"[SUBTREE] Fragment {fragment_idx}: '{fragment_text}' [words: {word_index_start}-{word_index_end}]")

                    # Create chunk with consistent order as line_chunker.py
                    chunk = {
                        "chunk_id": f"fragment_{line_id}_{fragment_idx}",
                        "source_chunk_id": source_chunk_id,  # Added reference to source line
                        "title": line_chunk.get("title", "Unknown"),
                        "line": line_chunk.get("line"),
                        "act": line_chunk.get("act"),
                        "scene": line_chunk.get("scene"),
                        "text": fragment_text,
                        "word_index": f"{word_index_start},{word_index_end}",
                        "syllables": total_syllables,
                        "POS": fragment_pos,
                        "mood": line_chunk.get("mood", "neutral"),
                        "word_count": len(word_tokens),
                        "fragment_position": fragment_idx,
                        "total_fragments_in_line": None  # Will update this later
                    }
                    chunks.append(chunk)
                    used_indices.update(range(word_index_start, word_index_end + 1))
                    fragment_idx += 1

            # --- Fallback Strategy: Sliding window with no overlap ---
            if fragment_idx == 0:
                i = 0
                while i <= len(line_tokens) - self.min_words:
                    for window_size in range(self.max_words, self.min_words - 1, -1):
                        end = i + window_size
                        if end > len(line_tokens):
                            continue

                        if any(idx in used_indices for idx in range(i, end)):
                            continue

                        window_tokens = line_tokens[i:end]
                        if SPACY_AVAILABLE and all(hasattr(t, 'text') for t in window_tokens):
                            fragment_words = [t.text for t in window_tokens]
                            fragment_pos = [t.pos_ for t in window_tokens]
                        else:
                            fragment_words = window_tokens
                            fragment_pos = pos_tags[i:end] if i + window_size <= len(pos_tags) else [""] * len(window_tokens)
                            
                        fragment_text = " ".join(fragment_words).strip()
                        total_syllables = sum(self._count_syllables(str(word)) for word in fragment_words)

                        self.logger.debug(f"[FALLBACK] Fragment {fragment_idx}: '{fragment_text}' [words: {i}-{end - 1}]")

                        # Create chunk with consistent order as line_chunker.py
                        chunk = {
                            "chunk_id": f"fragment_{line_id}_{fragment_idx}",
                            "source_chunk_id": source_chunk_id,  # Added reference to source line
                            "title": line_chunk.get("title", "Unknown"),
                            "line": line_chunk.get("line"),
                            "act": line_chunk.get("act"),
                            "scene": line_chunk.get("scene"),
                            "text": fragment_text,
                            "word_index": f"{i},{end - 1}",
                            "syllables": total_syllables,
                            "POS": fragment_pos,
                            "mood": line_chunk.get("mood", "neutral"),
                            "word_count": len(window_tokens),
                            "fragment_position": fragment_idx,
                            "total_fragments_in_line": None  # Will update this later
                        }
                        chunks.append(chunk)
                        used_indices.update(range(i, end))
                        fragment_idx += 1
                        break  # break after first valid window at position i
                    i += 1

        # Update total_fragments_in_line for all chunks
        from collections import defaultdict
        line_to_count = defaultdict(int)
        for chunk in chunks:
            key = (chunk['title'], chunk['act'], chunk['scene'], chunk['line'])
            line_to_count[key] += 1
        for chunk in chunks:
            key = (chunk['title'], chunk['act'], chunk['scene'], chunk['line'])
            chunk['total_fragments_in_line'] = line_to_count[key]

        self.logger.info(f"Completed fragment chunking: created {len(chunks)} fragments")
        return chunks

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("Use chunk_from_line_chunks instead")