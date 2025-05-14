from typing import List, Optional, Dict, Any, cast, Union
from modules.utils.logger import CustomLogger
from modules.translator.types import CandidateQuote
from modules.validation.validator import Validator
from modules.translator.rag_caller import RagCaller
from modules.translator.selector import Selector
from modules.translator.assembler import Assembler
from modules.translator.scene_saver import SceneSaver
from modules.translator.config import get_config, update_config, get_output_dir
from modules.rag.used_map import UsedMap
from dotenv import load_dotenv
import re


load_dotenv()

class TranslationManager:
    def __init__(self, custom_config: Optional[Dict[str, Any]] = None, logger: Optional[CustomLogger] = None):
        self.logger = logger or CustomLogger("TranslationManager")
        self.logger.info("Initializing TranslationManager")

        # Load configuration
        self.config = get_config()
        if custom_config:
            update_config(custom_config)
            self.config = get_config()
        
        self.used_map: UsedMap = UsedMap(logger=self.logger)
        self.validator: Validator = Validator()
        self.rag: RagCaller = RagCaller(logger=self.logger)
        self.selector: Selector = Selector(
            used_map=self.used_map, 
            validator=self.validator, 
            mmr_lambda=self.config['mmr_lambda'],
            logger=self.logger
        )
        self.assembler: Assembler = Assembler(
            model_provider=self.config['model_provider'],
            model_name=self.config['model_name'],
            temperature=self.config['temperature']
        )

        self.translation_id: Optional[str] = None

    def _generate_translation_id(self) -> str:
        import uuid
        return str(uuid.uuid4())[:8]

    def start_translation_session(self, translation_id: Optional[str] = None):
        self.translation_id = translation_id or self._generate_translation_id()
        self.logger.info(f"Starting translation session: {self.translation_id}")
        self.used_map.load(self.translation_id)

    def _count_syllables(self, text: str) -> int:
        """Count syllables in text using the same method as in the chunking scripts."""
        words = text.split()
        total_syllables = 0
        
        for word in words:
            # Skip if it's punctuation or doesn't contain at least one letter
            if not any(c.isalpha() for c in word):
                continue

            word = word.lower()
            if len(word) <= 3:
                total_syllables += 1
                continue
                
            # Remove trailing e as it's often silent
            if word.endswith('e'):
                word = word[:-1]
                
            # Count vowel groups
            import re
            vowels = re.findall(r'[aeiouy]+', word)
            total_syllables += max(1, len(vowels))
        
        return total_syllables

    def translate_line(self, modern_line: str, selector_results: Dict[str, List[CandidateQuote]], 
                      use_hybrid_search: Optional[bool] = None, mmr_lambda: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Modified to use config values as defaults
        """
        if not self.translation_id:
            raise RuntimeError("Translation session not started. Call start_translation_session().")

        # Use config defaults if not specified
        use_hybrid_search = use_hybrid_search if use_hybrid_search is not None else (self.config['default_search_mode'] == 'hybrid')
        mmr_lambda = mmr_lambda if mmr_lambda is not None else self.config['mmr_lambda']

        search_type = "HYBRID" if use_hybrid_search else "STANDARD"
        self.logger.info(f"Translating line using {search_type} search: {modern_line}")
        
        # Track if results are from hybrid search
        is_hybrid_results = use_hybrid_search  

        try:
            # If we're using hybrid search and weren't given results, get them now
            if use_hybrid_search and not selector_results:
                try:
                    self.logger.info(f"[HYBRID] Performing initial hybrid search for: '{modern_line}'")
                    selector_results = self.rag.hybrid_search(modern_line, top_k=15)
                    is_hybrid_results = True
                    
                    # Verify the structure of the results
                    total_candidates = 0
                    if "line" in selector_results:
                        total_candidates += len(selector_results["line"])
                    if "phrases" in selector_results:
                        total_candidates += len(selector_results["phrases"])
                    if "fragments" in selector_results:
                        total_candidates += len(selector_results["fragments"])
                    
                    self.logger.info(f"[HYBRID] Hybrid search returned results: {total_candidates} total candidates")
                    
                    # Check if we got enough candidates to proceed
                    if total_candidates == 0:
                        self.logger.warning("[HYBRID] No candidates returned from hybrid search")
                        # Skip to failsafe immediately if there are no candidates
                        raise KeyError("No candidates in hybrid search results")
                        
                except Exception as e:
                    self.logger.error(f"[HYBRID] Error performing hybrid search: {e}")
                    
                    # Go directly to failsafe
                    self.logger.info("[HYBRID] Going directly to failsafe due to error in hybrid search")
                    
                    # Perform a normal search to get at least one line for the failsafe
                    try:
                        fallback_results = self.rag.retrieve_all(modern_line, top_k=1)
                        if fallback_results.get("line") and len(fallback_results["line"]) > 0:
                            self.logger.info("[HYBRID] FAILSAFE: Using top line quote from fallback search")
                            top_line = fallback_results["line"][0]
                            return self._create_single_quote_result(top_line, modern_line)
                    except Exception as fallback_error:
                        self.logger.error(f"[HYBRID] Error in fallback search: {fallback_error}")
                    
                    # If we can't get even a fallback line, return None
                    self.logger.error("[HYBRID] Unable to retrieve any lines for failsafe, translation failed")
                    return None

            # === STEP 1: Prompt Preparation ===
            self.logger.debug(f"[{search_type}] STEP 1: Calling Selector.prepare_prompt_structure")
            min_options_per_level = 3  # Minimum quotes we want per level
            
            try:
                prompt_structure, temp_map = self.selector.prepare_prompt_structure(
                    selector_results, 
                    min_options=min_options_per_level,
                    mmr_lambda=mmr_lambda
                )                
                # Calculate syllable count for the modern line
                target_syllables = self._count_syllables(modern_line)
                self.logger.info(f"Modern line has {target_syllables} syllables")
                
                # Add the target syllables in a special entry that follows the same pattern
                # as the existing structure but won't be treated as a quote option
                prompt_structure["metadata"] = [{"target_syllables": target_syllables}]

                # Count total valid options across all levels
                total_options = sum(len(options) for options in prompt_structure.values())
                
                # Check if we have enough options total (at least 3 across all levels)
                if total_options < 3:
                    self.logger.warning(f"[{search_type}] STEP 1 INITIAL: Only {total_options} valid candidates total. Attempting to retrieve more...")
                    
                    # Attempt to get more candidates with extended search - double the top_k
                    try:
                        if use_hybrid_search:
                            extended_results = self.rag.hybrid_search(modern_line, top_k=25)
                            self.logger.info(f"[HYBRID] Extended hybrid search complete")
                        else:
                            extended_results = self.rag.retrieve_all(modern_line, top_k=20)
                        
                        # Try again with the extended results
                        prompt_structure, temp_map = self.selector.prepare_prompt_structure(extended_results, min_options=min_options_per_level)
                        
                        # Count options again
                        total_options = sum(len(options) for options in prompt_structure.values())
                    except Exception as e:
                        self.logger.error(f"[{search_type}] Error in extended search: {e}")
                        total_options = 0  # Force failsafe path
                    
                    if total_options < 1:
                        raise ValueError(f"[{search_type}] Insufficient candidates after extended search")
                    else:
                        self.logger.info(f"[{search_type}] STEP 1 EXTENDED: Retrieved {total_options} valid candidates after extended search.")
                
                self.logger.debug(f"[{search_type}] STEP 1 COMPLETE: Prompt structure created with {total_options} total options")

                # === STEP 2: LLM Assembly ===
                # Adjust assembly retry logic based on search type
                self.logger.debug(f"[{search_type}] STEP 2: Calling Assembler.assemble_line")
                
                # For hybrid search, we only try once; for standard search we allow retries
                max_retries = 0 if use_hybrid_search else 1  # 0 means one try, no retries
                assembled_result = self.assembler.assemble_line(modern_line, prompt_structure, max_retries=max_retries)
                
                if not assembled_result:
                    self.logger.warning(f"[{search_type}] STEP 2 FAILED: Assembler failed after {max_retries + 1} attempts.")
                    
                    # If standard search failed, try hybrid as fallback
                    if not use_hybrid_search:
                        self.logger.info("[STANDARD] FALLBACK: Attempting hybrid search")
                        return self.translate_line(modern_line, {}, use_hybrid_search=True)
                    else:
                        # Hybrid search already failed, raise exception to trigger failsafe
                        raise ValueError("[HYBRID] Assembly failed, triggering failsafe")
                
                self.logger.info(f"[{search_type}] STEP 2 COMPLETE: Assembler returned result successfully")
                
                # === STEP 3: Extract result and fix temp_ids format if needed ===
                assembled_text = assembled_result.get("text", "").strip()
                temp_ids_used = assembled_result.get("temp_ids", [])

                if isinstance(temp_ids_used, dict):
                    self.logger.warning("STEP 3: LLM returned temp_ids as dict, converting to list.")
                    temp_ids_used = list(temp_ids_used.values())

                if not assembled_text or not temp_ids_used:
                    self.logger.warning("STEP 3 FAILED: Missing text or temp_ids in assembler output.")
                    raise ValueError("Missing text or temp_ids in assembler output")
                self.logger.debug("STEP 3 COMPLETE: Assembled text and temp_ids extracted.")
                
                # Log the actual assembled content for debugging
                self.logger.info(f"Assembled text: '{assembled_text}' using temp_ids: {temp_ids_used}")

                # === STEP 4: Validation of returned IDs ===
                self.logger.debug("STEP 4: Validating temp_ids_used and looking up candidates")
                valid_temp_ids = set(temp_map.keys())
                invalid_ids = [tid for tid in temp_ids_used if tid not in valid_temp_ids]
                if invalid_ids:
                    self.logger.warning(f"STEP 4 FAILED: Invalid temp_ids in result: {invalid_ids}")
                    raise ValueError(f"Invalid temp_ids in result: {invalid_ids}")

                used_candidates = [temp_map[cid] for cid in temp_ids_used]
                references = [c.reference for c in used_candidates]
                
                # Log references for debugging
                for i, ref in enumerate(references):
                    self.logger.debug(f"Reference {i+1}: {ref}")
                    
                self.logger.debug("STEP 4 COMPLETE: Used candidates and references extracted.")

                # === STEP 5: Line Validation ===
                self.logger.debug("STEP 5: Running final validator.validate_line")
                validation_result = self.validator.validate_line(assembled_text, references)
                if not validation_result:
                    self.logger.warning("STEP 5 FAILED: Validator failed on assembled line.")
                    raise ValueError("Validator failed on assembled line")
                self.logger.debug("STEP 5 COMPLETE: Validator confirmed line is valid.")

                # === STEP 6: Mark Used ===
                self.logger.debug("STEP 6: Updating used map with references.")
                for ref in references:
                    # Create reference key from reference parts with better handling of null/None values
                    title = ref.get('title', '')
                    act = ref.get('act', '')
                    scene = ref.get('scene', '')
                    line = ref.get('line', '')
                    
                    # Create a consistent reference key
                    ref_key = f"{title}|{act if act is not None else 'NULL'}|{scene if scene is not None else 'NULL'}|{line}"
                    
                    # Extract word indices
                    word_index_str = ref.get("word_index", "")
                    if word_index_str and isinstance(word_index_str, str):
                        try:
                            # Handle different word_index formats
                            word_indices = []
                            if "," in word_index_str:
                                start, end = map(int, word_index_str.split(","))
                                word_indices = list(range(start, end + 1))
                            elif "-" in word_index_str:
                                start, end = map(int, word_index_str.split("-"))
                                word_indices = list(range(start, end + 1))
                            else:
                                # Try single number case
                                try:
                                    index = int(word_index_str.strip())
                                    word_indices = [index]
                                except ValueError:
                                    self.logger.warning(f"Invalid word_index format: {word_index_str}")
                                    continue
                            
                            # Log the reference key and word indices for debugging
                            self.logger.debug(f"Marking used: [{ref_key}] -> {word_indices}")
                            
                            # Mark as used
                            self.used_map.mark_used(ref_key, word_indices)
                            
                        except (ValueError, IndexError) as e:
                            self.logger.warning(f"Invalid word_index format: {word_index_str} - {e}")
                    else:
                        self.logger.warning(f"Missing or invalid word_index in reference: {ref}")
                
                self.used_map.save()
                self.logger.debug("STEP 6 COMPLETE: Used map updated and saved.")

                # === STEP 7: Return Final Output ===
                self.logger.info("Line translated and validated successfully.")
                
                # Create the full reference information
                full_references = []
                for cid, ref in zip(temp_ids_used, references):
                    full_ref = {
                        "temp_id": cid,
                        "title": ref.get("title", "Unknown"),
                        "act": ref.get("act", "Unknown"),
                        "scene": ref.get("scene", "Unknown"),
                        "line": ref.get("line", "Unknown"),
                        "word_index": ref.get("word_index", "0,0")
                    }
                    full_references.append(full_ref)
                
                return {
                    "text": assembled_text,
                    "temp_ids": temp_ids_used,  # Keep temp_ids for debugging
                    "references": full_references,  # Use the improved references
                    "original_modern_line": modern_line,  # Store the original modern line
                    "search_type": search_type  # Track which search method was used
                }
                
            except Exception as prompt_error:
                # Any error in the main assembly process will trigger the failsafe
                self.logger.error(f"[{search_type}] Error in translation process: {prompt_error}")
                
                # Try to get a single line quote for the failsafe
                self.logger.info(f"[{search_type}] FAILSAFE: Attempting to retrieve a single line quote")
                
                # First try the original selector_results if they exist
                if selector_results and "line" in selector_results and selector_results["line"]:
                    self.logger.info(f"[{search_type}] FAILSAFE: Using top line quote from original results")
                    top_line = selector_results["line"][0]
                    return self._create_single_quote_result(top_line, modern_line)
                
                # If that fails, try a fresh search
                try:
                    self.logger.info(f"[{search_type}] FAILSAFE: Performing new search for a single line quote")
                    fallback_results = self.rag.retrieve_all(modern_line, top_k=1)
                    if fallback_results.get("line") and fallback_results["line"]:
                        self.logger.info(f"[{search_type}] FAILSAFE: Using top line quote from fallback search")
                        top_line = fallback_results["line"][0]
                        return self._create_single_quote_result(top_line, modern_line)
                except Exception as fallback_error:
                    self.logger.error(f"[{search_type}] Error in failsafe search: {fallback_error}")
                
                # If we still can't get a line, we have to give up
                self.logger.error(f"[{search_type}] All translation attempts failed, including failsafe")
                return None

        except Exception as e:
            self.logger.error(f"Unhandled translation error: {e}")
            self.log_decision({
                "status": "error",
                "input": modern_line,
                "error": str(e)
            })
            
            # Final emergency failsafe - try one last time to get any line
            try:
                self.logger.info("EMERGENCY FAILSAFE: Attempting final search for any line")
                emergency_results = self.rag.retrieve_all(modern_line, top_k=1)
                if emergency_results.get("line") and emergency_results["line"]:
                    self.logger.info("EMERGENCY FAILSAFE: Found a line to use")
                    top_line = emergency_results["line"][0]
                    return self._create_single_quote_result(top_line, modern_line)
            except Exception:
                pass
                
            return None

    def _create_single_quote_result(self, quote: CandidateQuote, modern_line: str) -> Dict[str, Any]:
        """Create a result using a single quote directly."""
        self.logger.info(f"Creating FAILSAFE result from single quote: '{quote.text}'")
        
        # Mark the quote as used in the used_map
        title = quote.reference.get('title', '')
        act = quote.reference.get('act', '')
        scene = quote.reference.get('scene', '')
        line = quote.reference.get('line', '')
        ref_key = f"{title}|{act if act is not None else 'NULL'}|{scene if scene is not None else 'NULL'}|{line}"
        
        word_index_str = quote.reference.get("word_index", "")
        if word_index_str and isinstance(word_index_str, str):
            try:
                if "," in word_index_str:
                    start, end = map(int, word_index_str.split(","))
                    word_indices = list(range(start, end + 1))
                else:
                    word_indices = [int(word_index_str.strip())]
                
                self.used_map.mark_used(ref_key, word_indices)
                self.used_map.save()
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Invalid word_index format in failsafe: {word_index_str} - {e}")
        
        # Create reference information
        reference = {
            "temp_id": "failsafe_1",
            "title": quote.reference.get("title", "Unknown"),
            "act": quote.reference.get("act", "Unknown"),
            "scene": quote.reference.get("scene", "Unknown"),
            "line": quote.reference.get("line", "Unknown"),
            "word_index": quote.reference.get("word_index", "0,0")
        }
        
        return {
            "text": quote.text,
            "temp_ids": ["failsafe_1"],
            "references": [reference],
            "original_modern_line": modern_line,
            "is_failsafe": True  # Flag to indicate this was a failsafe result
        }

    def translate_group(self, modern_lines: List[str], use_hybrid_search: bool = False) -> List[Dict[str, Any]]:
        """Translate a group of modern lines."""
        self.logger.info(f"Translating group of {len(modern_lines)} lines with hybrid_search={use_hybrid_search}")
        results = []
        
        for line in modern_lines:
            if use_hybrid_search:
                selector_results = self.rag.hybrid_search(line)
                # Don't add _is_hybrid flag here
            else:
                selector_results = self.rag.retrieve_all(line)
            
            result = self.translate_line(line, selector_results, use_hybrid_search=use_hybrid_search)
            if result is not None:
                results.append(result)
        
        return results

    def translate_scene(self, scene_lines: List[str]) -> List[Dict[str, Any]]:
        self.logger.info(f"Starting scene translation: {len(scene_lines)} lines")
        translated_scene: List[Dict[str, Any]] = []

        for i, line in enumerate(scene_lines):
            self.logger.info(f"Translating line {i + 1}/{len(scene_lines)}")
            selector_results = self.rag.retrieve_all(line)
            translated = self.translate_line(line, selector_results)
            if translated:
                translated_scene.append(translated)
            else:
                self.logger.warning(f"Line {i + 1} failed translation and was skipped")

        self.logger.info(f"Completed scene translation: {len(translated_scene)} lines generated")
        return translated_scene

    def save_translated_scene(self, act: str, scene: str, translated_lines: List[Dict[str, Any]], original_lines: Optional[List[str]] = None) -> str:
        """
        Save translated scene to file.
        
        Args:
            act: Act identifier
            scene: Scene identifier
            translated_lines: List of translated line dictionaries
            original_lines: Optional list of original modern lines
            
        Returns:
            Path to the saved file
        """
        if not self.translation_id:
            raise RuntimeError("Translation session not started. Call start_translation_session().")
        
        # Use SceneSaver to save the translation
        saver = SceneSaver(translation_id=self.translation_id)
        
        # If original_lines is None, pass an empty list instead
        lines_to_save = original_lines if original_lines is not None else []
        
        saver.save_scene(
            act=act,
            scene=scene,
            translated_lines=translated_lines,
            original_lines=lines_to_save,
            checkpoint_interval=self.config['checkpoint_interval']
        )
        
        # Return the output directory path
        output_dir = get_output_dir(self.translation_id)
        self.logger.info(f"Saved translated scene to {output_dir}")
        return output_dir

    def get_usage_map(self) -> Dict[str, Any]:
        return self.used_map.get_used_map()

    def log_decision(self, details: Dict[str, Any]) -> None:
        self.logger.debug(f"Decision Log: {details}")