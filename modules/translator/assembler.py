# modules/translator/assembler.py

import json
import re
import importlib.util
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Union
from modules.translator.types import CandidateQuote
from modules.utils.logger import CustomLogger
from openai import OpenAI
from anthropic import Anthropic
from anthropic.types import TextBlock

load_dotenv()

class Assembler:
    def __init__(
        self, 
        config_path: str = "modules/playwright/config.py",
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        self.logger = CustomLogger("Assembler")
        self.logger.info("Initializing Assembler")

        self.config = self._load_config(config_path)
        
        # Override config values with provided parameters if specified
        self.model_provider = model_provider or self.config.get("model_provider", "openai")
        self.model_name = model_name or self.config.get("model_name", "gpt-4o")
        self.temperature = temperature or self.config.get("temperature", 0.7)

        self.openai_client: Optional[OpenAI] = None
        self.anthropic_client: Optional[Anthropic] = None
        self._init_model_client()

    def _load_config(self, path: str) -> Dict[str, Any]:
        spec = importlib.util.spec_from_file_location("config", path)
        if not spec or not spec.loader:
            raise ImportError("Could not load configuration")

        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        return {
            key: getattr(config_module, key)
            for key in dir(config_module)
            if not key.startswith("__")
        }

    def _init_model_client(self):
        if self.model_provider == "anthropic":
            self.anthropic_client = Anthropic()
        else:
            self.openai_client = OpenAI()

    def assemble_line(self, modern_line: str, prompt_data: Dict[str, List[Dict[str, Any]]], max_retries: int = 1) -> Optional[Dict[str, Any]]:
        """Main method to assemble a translated line using only the provided quotes."""
        self.logger.info("Beginning line assembly")
        self.logger.debug(f"Modern line: {modern_line}")
        retries = 0
        
        # Create a copy of prompt_data that we can modify during retries
        import copy
        working_prompt_data = copy.deepcopy(prompt_data)

        while retries <= max_retries:
            if retries > 0:
                # Skip the "just shuffle" step and go straight to shuffle + remove quotes
                self.logger.info("Retry: Shuffling and potentially removing quotes")
                for form in working_prompt_data:
                    if len(working_prompt_data[form]) > 1:
                        working_prompt_data[form].pop()  # Remove one option
                    import random
                    random.shuffle(working_prompt_data[form])
            
            # Generate the prompt and get LLM response
            prompt = self._build_prompt(modern_line, working_prompt_data)
            response = self._call_model(prompt)
            parsed = self._extract_output(response)

            # Check if we got a valid response with text
            if parsed is None or "text" not in parsed:
                self.logger.warning(f"Failed to parse LLM output on attempt {retries + 1}")
                retries += 1
                continue

            assembled_line = parsed["text"]

            # Validate the assembled line and identify the quotes used
            validation_result = self._mini_validate(assembled_line, working_prompt_data)
            if isinstance(validation_result, dict):
                self.logger.info("Mini-validation succeeded")
                return validation_result  # Contains 'text' and 'temp_ids'

            self.logger.warning(f"Mini-validation failed on attempt {retries + 1}")
            retries += 1

        self.logger.error(f"Assembler failed after {max_retries} retries")
        return None

    def _build_prompt(self, modern_line: str, quote_options: Dict[str, List[Dict[str, Any]]]) -> str:
        quote_list = []
        
        # Extract target syllables from the metadata if it exists
        target_syllables = None
        if "metadata" in quote_options and quote_options["metadata"] and isinstance(quote_options["metadata"][0], dict):
            target_syllables = quote_options["metadata"][0].get("target_syllables")
        
        # Generate the quote options list
        for form, options in quote_options.items():
            # Skip metadata - it's not a quote option
            if form == "metadata":
                continue
                
            for opt in options:
                temp_id = opt.get("temp_id")
                text = opt.get("text", "").strip()
                score = opt.get("score", None)
                # Include syllable count in the quote information if available
                syllables = opt.get("syllables", None)
                
                line = f"[{form.upper()}] {temp_id}: \"{text}\""
                if score is not None:
                    line += f" (score: {score:.4f})"
                if syllables is not None:
                    line += f" (syllables: {syllables})"
                
                quote_list.append(line)

        quotes_str = "\n".join(quote_list)
        
        # Create the syllable instruction if we have target syllables
        syllable_instruction = ""
        if target_syllables:
            syllable_instruction = f"""
    IMPORTANT: The modern line has approximately {target_syllables} syllables. Try to assemble a line with a similar syllable count (within 25% if possible).
    """

        return f"""
    You are a playwright assistant generating Shakespeare-style dialog using a modern play line and selected source quotes. You use quotes from Shakespeare as puzzle pieces, fit together to match as closely as possible the modern play line.

    Your job:
    - Translate the modern English line into dramatic Shakespearean verse.
    - Use ONLY the provided Shakespearean quotes, EXACTLY as written - NO modifications whatsoever.
    - You MUST use the entire Shakespearean quote as provided - do not omit any words from a quote you choose. Do not add any words from a quote you choose.
    - You may select 1 to 3 of the Shakespearean quote options (they can be lines, phrases, or fragments).
    - When combining Shakespearean quote options, try to match the number of syllables listed for those quotes to the number of syllables in the modern line.
    - You may only combine whole Shakespearean quotes - no partial usage is allowed.
    - You may rearrange the order of the Shakespearean quotes but not change their internal wording.
    - No proper nouns may be used.
    - Return ONLY the final assembled line, without listing the temp_ids or any other information.
    {syllable_instruction}

    Modern play line:
    "{modern_line}"

    Here are your options:
    {quotes_str}

    Your response should contain ONLY the assembled text, with no additional commentary.
    """.strip()

    def _call_model(self, prompt: str) -> str:
        if self.anthropic_client:
            response = self.anthropic_client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            content = "".join(
                block.text for block in response.content
                if isinstance(block, TextBlock)
            )
            return content.strip()

        if self.openai_client:
            response = self.openai_client.chat.completions.create(
                model=self.model_name,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": "You are a playwright assistant generating lines from source quotes."},
                    {"role": "user", "content": prompt}
                ]
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""

        raise RuntimeError("No valid LLM client configured.")

    def _extract_output(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Parses the LLM output and extracts the assembled line.
        """
        self.logger.debug(f"Raw LLM response: {response_text[:100]}...")  # Log first 100 chars
        
        try:
            # First check if the response is not empty
            if not response_text or response_text.isspace():
                self.logger.error("Empty or whitespace-only response from LLM")
                return None
                
            # Clean up the response
            cleaned = response_text.strip()
            
            # Remove any triple backticks if present
            cleaned = re.sub(r"^```(?:json)?\n?|```$", "", cleaned, flags=re.MULTILINE)
            
            # Try to extract JSON if the model still tried to provide it
            try:
                json_pattern = r'\{.*\}'
                json_match = re.search(json_pattern, cleaned, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(0)
                    self.logger.debug(f"Extracted JSON: {json_str[:100]}...")
                    
                    data = json.loads(json_str)
                    if "text" in data:
                        return {"text": data["text"]}
            except (json.JSONDecodeError, AttributeError):
                # Not JSON or couldn't extract, proceed with the cleaned text
                pass
            
            # If no JSON structure was found or parsed, use the cleaned text directly
            return {"text": cleaned}
            
        except Exception as e:
            self.logger.warning(f"Error parsing JSON output: {e}")
            self.logger.debug(f"Response causing error: {response_text[:200]}...")
            
        return None

    def _mini_validate(self, assembled_line: str, quote_data: Dict[str, List[Dict[str, Any]]]) -> Union[Dict[str, Any], bool]:
        """
        Validate the assembled line by identifying which quotes were used in order.
        
        Returns a dict with 'text' and 'temp_ids' if validation succeeds, or False if validation fails.
        """
        self.logger.info("Running mini-validation on assembled line")
        self.logger.debug(f"Assembled line: '{assembled_line}'")
        
        # Function to normalize text to alphanumeric only
        def normalize_text(text):
            return ''.join(c.lower() for c in text if c.isalnum())
        
        # Normalize the assembled line for comparison
        normalized_assembled = normalize_text(assembled_line)
        self.logger.debug(f"Normalized assembled: '{normalized_assembled}'")
        
        # Collect all quotes from all levels and normalize them
        all_quotes = []
        for form, quotes in quote_data.items():
            for quote in quotes:
                all_quotes.append({
                    "temp_id": quote["temp_id"],
                    "original": quote["text"],
                    "normalized": normalize_text(quote["text"])
                })
        
        # Sort quotes by length (descending) to match larger quotes first
        all_quotes.sort(key=lambda q: len(q["normalized"]), reverse=True)
        
        # Track the temp_ids of the quotes used, in order
        used_temp_ids = []
        remaining_text = normalized_assembled
        available_quotes = all_quotes.copy()
        
        # Maximum of 3 quotes allowed
        for position in range(3):
            if not remaining_text:  # No more text to match
                break
                
            found_match = False
            for i, quote in enumerate(available_quotes):
                # Check if this quote is at the beginning of the remaining text
                if remaining_text.startswith(quote["normalized"]):
                    # Found a match at the beginning
                    used_temp_ids.append(quote["temp_id"])
                    self.logger.debug(f"Match at position {position+1}: {quote['temp_id']} - '{quote['original']}'")
                    
                    # Remove the matched text from the beginning
                    remaining_text = remaining_text[len(quote["normalized"]):]
                    
                    # Remove this quote from available options
                    available_quotes.pop(i)
                    
                    found_match = True
                    break
            
            if not found_match and remaining_text:
                # If we can't match the beginning of the remaining text, validation fails
                self.logger.warning(f"No matching quote found at the beginning of remaining text: '{remaining_text}'")
                return False
        
        # If we've matched all text, validation succeeds
        if not remaining_text:
            self.logger.info(f"Validation succeeded. Used quotes in order: {used_temp_ids}")
            return {
                "text": assembled_line,
                "temp_ids": used_temp_ids
            }
        
        # If we've used 3 quotes but text still remains, validation fails
        self.logger.warning(f"Validation failed. Text remains after 3 quotes: '{remaining_text}'")
        return False

    def reformat_result(self, assembled: Dict[str, Any], references: List[Dict[str, str]]) -> Dict[str, Any]:
        return {
            "text": assembled["text"],
            "temp_ids": assembled["temp_ids"],
            "references": references
        }