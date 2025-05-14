"""
Phrase chunker module for Shakespeare AI project.

This module provides functionality to chunk Shakespeare's text into phrases
based on punctuation breaks, preserving the relationship to parent lines.
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


class PhraseChunker(ChunkBase):
    """Chunker for processing Shakespeare's text into phrases.

    This chunker splits text based on punctuation breaks (periods, commas, etc.)
    and maintains the relationship to the original line.
    """

    def __init__(self, logger: Optional[CustomLogger] = None):
        super().__init__(chunk_type='phrase')
        self.logger = logger or CustomLogger("PhraseChunker")
        self.logger.info("Initializing PhraseChunker")

        if not SPACY_AVAILABLE:
            self.logger.warning("spaCy is not available - using fallback tokenization")
            self.logger.info("To install spaCy: pip install spacy && python -m spacy download en_core_web_sm")

        self.phrase_pattern = re.compile(r'([.!?;:])')
        self.logger.debug("Compiled regular expressions for text parsing")

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
        self.logger.info("Starting phrase chunking from line chunks")
        self.logger.debug(f"Processing {len(line_chunks)} line chunks")
        chunks = []

        for line_chunk in line_chunks:
            line_text = line_chunk['text']
            line_id = line_chunk['chunk_id']
            source_chunk_id = line_chunk['chunk_id']  # Store original chunk_id
            
            # Normalize the text
            line_text = self._normalize_quotes(line_text)

            # Process line with spaCy and get word tokens (no punctuation/whitespace)
            tokens = self._process_line_with_spacy(line_text)
            
            # Get just the text of each token
            if SPACY_AVAILABLE and all(hasattr(t, 'text') for t in tokens):
                token_words = [t.text for t in tokens]
                # Get POS tags when available
                token_pos = [t.pos_ for t in tokens]
            else:
                token_words = tokens
                token_pos = [""] * len(tokens)

            # Split the line into phrases using punctuation
            phrase_pattern = re.compile(r'([.!?;:])')
            major_parts = phrase_pattern.split(line_text)

            phrases = []
            i = 0
            while i < len(major_parts):
                if i + 1 < len(major_parts) and phrase_pattern.match(major_parts[i + 1]):
                    phrases.append(major_parts[i] + major_parts[i + 1])
                    i += 2
                else:
                    if major_parts[i].strip():
                        phrases.append(major_parts[i])
                    i += 1

            final_phrases = []
            for phrase in phrases:
                comma_parts = phrase.split(',')
                for j, part in enumerate(comma_parts):
                    cleaned = part.strip()
                    if cleaned:
                        if j < len(comma_parts) - 1:
                            final_phrases.append(cleaned + ',')
                        else:
                            final_phrases.append(cleaned)

            used_indices = set()

            for phrase_idx, phrase in enumerate(final_phrases):
                # Process the phrase with spaCy, excluding punctuation/whitespace
                phrase_tokens = self._process_line_with_spacy(phrase)
                
                if SPACY_AVAILABLE and all(hasattr(t, 'text') for t in phrase_tokens):
                    phrase_words = [t.text for t in phrase_tokens]
                else:
                    phrase_words = phrase_tokens
                
                phrase_text = " ".join(phrase_words).strip()

                if len(phrase_words) < 3:
                   continue  # Skip phrases with fewer than 3 words

                if not phrase_words:
                    continue

                try:
                    # Find the first matching slice in token_words
                    for i in range(len(token_words) - len(phrase_words) + 1):
                        if token_words[i:i+len(phrase_words)] == phrase_words:
                            phrase_start = i
                            phrase_end = i + len(phrase_words) - 1
                            if any(idx in used_indices for idx in range(phrase_start, phrase_end + 1)):
                                raise ValueError("Overlapping phrase indices")
                            break
                    else:
                        raise ValueError("Phrase words not aligned")
                except ValueError:
                    self.logger.warning(f"Could not align phrase in token list: {phrase_words}")
                    continue

                phrase_pos_tags = token_pos[phrase_start:phrase_end + 1] if len(token_pos) > phrase_end else []
                total_syllables = sum(self._count_syllables(str(word)) for word in phrase_words)

                # Create the final chunk dictionary in the same order as line_chunker.py
                chunk = {
                    "chunk_id": f"phrase_{line_id}_{phrase_idx}",
                    "source_chunk_id": source_chunk_id,  # Added reference to source line
                    "title": line_chunk.get("title", "Unknown"),
                    "line": line_chunk.get("line"),
                    "act": line_chunk.get("act"),
                    "scene": line_chunk.get("scene"),
                    "text": phrase_text,
                    "word_index": f"{phrase_start},{phrase_end}",
                    "syllables": total_syllables,
                    "POS": phrase_pos_tags,
                    "mood": line_chunk.get("mood", "neutral"),
                    "word_count": len(phrase_words),
                    "phrase_position": phrase_idx,
                    "total_phrases_in_line": len(final_phrases),
                    "ends_with_punctuation": bool(re.search(r'[.!?;:,]$', phrase))
                }
                chunks.append(chunk)
                used_indices.update(range(phrase_start, phrase_end + 1))
                self.logger.debug(
                    f"Created phrase chunk {chunk['chunk_id']} from line {line_id}: {len(phrase)} chars, {len(phrase_words)} words, word_index: {phrase_start}-{phrase_end}"
                )

        self.logger.info(f"Completed phrase chunking: created {len(chunks)} chunks from line chunks")
        return chunks

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("Use chunk_from_line_chunks instead")