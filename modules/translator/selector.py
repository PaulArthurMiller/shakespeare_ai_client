# modules/translator/selector.py

from typing import List, Dict, Optional, Union, Tuple, Any, cast
from modules.translator.types import CandidateQuote, ReferenceDict
from modules.validation.validator import Validator
from modules.rag.used_map import UsedMap
from modules.utils.logger import CustomLogger


class Selector:
    def __init__(
        self,
        used_map: UsedMap,
        validator: Optional[Validator] = None,
        mmr_lambda: float = 0.6,  # Add mmr_lambda parameter with default value
        logger: Optional[CustomLogger] = None
    ):
        self.logger = logger or CustomLogger("Selector")
        self.used_map = used_map
        self.validator = validator or Validator()
        self.mmr_lambda = mmr_lambda  # Store mmr_lambda as instance variable

    def filter_candidates(self, candidates: List[CandidateQuote]) -> List[CandidateQuote]:
        """
        Filter candidates by removing any that:
        - Have proper nouns (POS == "PROPN")
        - Were already used (checked via UsedMap)
        - Have invalid reference structure
        """
        filtered = []
        
        for candidate in candidates:
            try:
                reference = candidate.reference

                # Skip if reference is not a dictionary
                if not isinstance(reference, dict):
                    self.logger.warning("Candidate reference is not a dict, skipping.")
                    continue

                # Check for proper nouns - more rigorous check
                has_proper_noun = False
                
                # Check "POS" field if it exists
                if "POS" in reference:
                    pos_tags = reference.get("POS", [])
                    if isinstance(pos_tags, list) and "PROPN" in pos_tags:
                        # Only check if the first word is a proper noun by its POS tag
                        if len(pos_tags) > 0 and pos_tags[0] == "PROPN":
                            self.logger.info("Skipping candidate due to proper noun at position 0 (from POS tag)")
                            has_proper_noun = True
                        else:
                            # For non-first words, any PROPN is a problem
                            for i, tag in enumerate(pos_tags):
                                if i > 0 and tag == "PROPN":
                                    self.logger.info(f"Skipping candidate due to proper noun at position {i} (from POS tag)")
                                    has_proper_noun = True
                                    break

                # Also check the text itself for capitalized words mid-sentence
                # but EXEMPT the first word unless it's tagged as PROPN
                if not has_proper_noun:
                    text = candidate.text
                    words = text.split()
                    for i, word in enumerate(words):
                        # Skip first word (naturally capitalized) and the word "I"
                        if i > 0 and word[0].isupper() and any(c.isalpha() for c in word) and word.lower() != "i":
                            self.logger.info(f"Skipping candidate due to capitalized word mid-sentence: '{word}'")
                            has_proper_noun = True
                            break

                if has_proper_noun:
                    continue

                # Get a unique reference key for the UsedMap
                title = reference.get("title", "Unknown")
                act = str(reference.get("act", ""))
                scene = str(reference.get("scene", ""))
                line = str(reference.get("line", ""))
                reference_key = f"{title}|{act}|{scene}|{line}"
                
                # Check if this reference was already used
                word_index_str = reference.get("word_index", "")
                if isinstance(word_index_str, str) and word_index_str:
                    if "," in word_index_str:
                        parts = word_index_str.split(",")
                        if len(parts) == 2:
                            try:
                                start, end = int(parts[0]), int(parts[1])
                                word_indices = list(range(start, end + 1))
                            except ValueError:
                                self.logger.warning(f"Invalid word_index format: {word_index_str}")
                                continue
                        else:
                            self.logger.warning(f"Invalid word_index format: {word_index_str}")
                            continue
                    else:
                        try:
                            word_indices = [int(word_index_str)]
                        except ValueError:
                            self.logger.warning(f"Invalid word_index format: {word_index_str}")
                            continue
                    
                    if self.used_map.was_used(reference_key, word_indices):
                        self.logger.info(f"Skipping candidate: already used {reference_key}:{word_indices}")
                        continue

                filtered.append(candidate)

            except Exception as e:
                self.logger.warning(f"Skipping candidate due to error: {e}")
                continue

        return filtered

    def rank_candidates(self, candidates: List[CandidateQuote], lambda_param: Optional[float] = None) -> List[CandidateQuote]:
        """
        Rank candidates using Maximal Marginal Relevance (MMR) to balance
        relevance and diversity.
        
        Args:
            candidates: List of candidate quotes
            lambda_param: Balance between relevance (1.0) and diversity (0.0),
                        default to self.mmr_lambda if not specified
        
        Returns:
            List of candidates reranked by MMR
        """
        # Use the instance variable if lambda_param not provided
        lambda_param = lambda_param if lambda_param is not None else self.mmr_lambda
    
        if not candidates:
            self.logger.warning("No candidates to rank")
            return []
            
        # First sort by similarity score (ascending = closer match)
        self.logger.info("Initial ranking of candidates by similarity score...")
        sorted_candidates = sorted(candidates, key=lambda c: c.score)
        
        # If we only have one candidate, just return it
        if len(sorted_candidates) <= 1:
            return sorted_candidates
        
        # Apply MMR
        self.logger.info(f"Applying Maximal Marginal Relevance (lambda={lambda_param})...")
        
        # Function to compute text similarity between two candidates
        def compute_similarity(text1: str, text2: str) -> float:
            """Compute simple text similarity based on shared words."""
            # Convert to lowercase and split into words
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            
            # Compute Jaccard similarity
            if not words1 or not words2:
                return 0.0
                
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            return len(intersection) / len(union)
        
        # Start with the most relevant candidate
        ranked_candidates = [sorted_candidates[0]]
        remaining_candidates = sorted_candidates[1:]
        
        # Iteratively select candidates with MMR
        while remaining_candidates and len(ranked_candidates) < len(sorted_candidates):
            max_mmr_score = -float('inf')
            max_mmr_idx = -1
            
            for i, candidate in enumerate(remaining_candidates):
                # Relevance score (convert score to a "higher is better" format)
                # Assuming lower scores are better in the original ranking
                relevance = 1.0 / (1.0 + candidate.score)  # Invert the score
                
                # Diversity score (max similarity to already selected candidates)
                max_similarity = 0.0
                for selected in ranked_candidates:
                    similarity = compute_similarity(candidate.text, selected.text)
                    max_similarity = max(max_similarity, similarity)
                
                # Calculate MMR score
                mmr_score = lambda_param * relevance - (1.0 - lambda_param) * max_similarity
                
                if mmr_score > max_mmr_score:
                    max_mmr_score = mmr_score
                    max_mmr_idx = i
            
            # Add the candidate with highest MMR score
            if max_mmr_idx != -1:
                ranked_candidates.append(remaining_candidates[max_mmr_idx])
                remaining_candidates.pop(max_mmr_idx)
            else:
                break
        
        # Log the reranked candidates
        for i, cand in enumerate(ranked_candidates):
            self.logger.debug(f"[{i}] Score: {cand.score:.4f} | {cand.text[:60]}")
        
        return ranked_candidates

    def analyze_candidate_diversity(self, candidates: List[CandidateQuote]) -> Dict[str, Any]:
        """
        Analyze the diversity of a set of candidates.
        
        Args:
            candidates: List of candidate quotes
            
        Returns:
            Dictionary with diversity metrics
        """
        if not candidates:
            return {"word_overlap": 0, "unique_words": 0, "total_words": 0, "diversity_score": 0}
        
        # Extract all words from all candidates
        all_words = []
        word_counts = {}
        
        for cand in candidates:
            words = [w.lower() for w in cand.text.split() if w.isalpha()]
            all_words.extend(words)
            
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Calculate metrics
        total_words = len(all_words)
        unique_words = len(word_counts)
        
        # Calculate average word repetition
        if total_words > 0:
            avg_repetition = sum(word_counts.values()) / len(word_counts)
        else:
            avg_repetition = 0
        
        # Calculate word overlap (higher means more redundancy)
        repeated_words = sum(1 for word, count in word_counts.items() if count > 1)
        if unique_words > 0:
            word_overlap = repeated_words / unique_words
        else:
            word_overlap = 0
        
        # Calculate diversity score (higher is better)
        if total_words > 0:
            diversity_score = unique_words / total_words
        else:
            diversity_score = 0
        
        return {
            "word_overlap": word_overlap,
            "unique_words": unique_words,
            "total_words": total_words,
            "avg_repetition": avg_repetition,
            "diversity_score": diversity_score,
            "most_repeated": sorted([(word, count) for word, count in word_counts.items() if count > 1], 
                                key=lambda x: x[1], reverse=True)[:5]
        }

    def prepare_prompt_structure(self, selector_results: Dict[str, List[CandidateQuote]], min_options: int = 3, mmr_lambda: float = 0.6) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, CandidateQuote]]:
        """
        Prepare the data structure for the LLM assembler prompt.
        Ensures we have at least min_options for each level if possible.
        Uses MMR to ensure diversity in the selected quotes.
        
        Args:
            selector_results: Results from RAG caller
            min_options: Minimum number of options desired per level
            mmr_lambda: Balance between relevance (1.0) and diversity (0.0) for MMR
        
        Returns:
            - prompt_data: Dict[level] -> List[dict with temp_id, text, score, form]
            - chunk_map: Dict[temp_id] -> CandidateQuote
        """
        self.logger.info("Preparing prompt structure from grouped candidates...")
        prompt_data: Dict[str, List[Dict[str, Any]]] = {"line": [], "phrases": [], "fragments": []}
        chunk_map: Dict[str, CandidateQuote] = {}

        max_options = 5  # Maximum options to include in prompt

        for level in ["line", "phrases", "fragments"]:
            candidates = selector_results.get(level, [])
            self.logger.info(f"Processing {level}: {len(candidates)} candidate(s)")

            # Step 1: Filter
            self.logger.info(f"Filtering {len(candidates)} candidate(s)...")
            filtered = self.filter_candidates(candidates)
            
            # Step 2: Check if we have enough options
            if len(filtered) < min_options:
                self.logger.warning(f"Only {len(filtered)} candidates passed filter at {level} level (minimum {min_options} desired)")
                
                # We'll still use what we have, even if it's fewer than desired
                if not filtered:
                    self.logger.warning(f"No candidates passed filter at {level} level.")
                    continue
            
            self.logger.info(f"{len(filtered)} candidate(s) passed filter")

            # Step 3: Rank with MMR for diversity on the FULL set of filtered candidates
            ranked = self.rank_candidates(filtered, lambda_param=mmr_lambda)
            
            # Step 4: Now limit to top N for prompt
            top_n = ranked[:max_options]
            self.logger.debug(f"Selected top {len(top_n)} diverse candidates for {level} level")
            
            # Step 5: Analyze diversity before and after MMR for logging
            before_diversity = self.analyze_candidate_diversity(filtered[:max_options])  # Original top candidates
            after_diversity = self.analyze_candidate_diversity(top_n)  # MMR ranked candidates
            
            # Log diversity metrics for debugging
            self.logger.info(f"Diversity metrics for {level} - Before MMR: score={before_diversity['diversity_score']:.3f}, " +
                            f"After MMR: score={after_diversity['diversity_score']:.3f}")
            
            if after_diversity['most_repeated']:
                self.logger.debug(f"Most repeated words after MMR: {after_diversity['most_repeated']}")

            # Step 6: Create prompt entries and map
            for i, cand in enumerate(top_n):
                if not isinstance(cand, CandidateQuote):
                    self.logger.warning(f"Invalid candidate object at {level}_{i + 1}: {type(cand)} — {cand}")
                    continue

                temp_id = f"{level}_{i + 1}"
                entry_dict = {
                    "temp_id": temp_id,
                    "text": cand.text,
                    "score": cand.score,
                    "form": level
                }

                # Add the syllable count if available in the metadata
                if isinstance(cand.reference, dict) and "syllables" in cand.reference:
                    entry_dict["syllables"] = cand.reference["syllables"]
                
                prompt_data[level].append(entry_dict)
                chunk_map[temp_id] = cand


            # Step 7: Logging the prompt items
            if prompt_data[level]:
                self.logger.debug(f"Prompt options for {level.upper()}:")
                for entry in prompt_data[level]:
                    if not isinstance(entry, dict):
                        self.logger.warning(f"Invalid entry for logging at {level}: {type(entry)} — {entry}")
                        continue
                    tid = entry.get("temp_id", "unknown_id")
                    txt = entry.get("text", "")
                    sc = entry.get("score", 0.0)
                    self.logger.debug(f"  {tid}: \"{txt}\" (score: {sc:.4f})")
            else:
                self.logger.warning(f"No prompt options available for {level.upper()}")

        return prompt_data, chunk_map
