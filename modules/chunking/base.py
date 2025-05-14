"""
Base chunker module for Shakespeare AI project.

This module provides the base class for all chunking operations.
Each specific chunker (line, phrase, fragment) will inherit from this base class.
"""
import os
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union


class ChunkBase(ABC):
    """Base class for all text chunkers in the Shakespeare AI project.
    
    This abstract class defines the common interface and utilities that all chunkers
    should implement. It handles shared functionality such as loading text, basic
    chunking operations, and saving chunks to JSON.
    """
    
    def __init__(self, chunk_type: str):
        """Initialize the chunker with a specific type.
        
        Args:
            chunk_type (str): The type of chunker (e.g., 'line', 'phrase', 'fragment')
        """
        self.chunk_type = chunk_type
        self.chunks = []
        
    def load_text(self, filepath: str) -> str:
        """Load text from a file.
        
        Args:
            filepath (str): Path to the text file
            
        Returns:
            str: The loaded text
            
        Raises:
            FileNotFoundError: If the file does not exist
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    
    @abstractmethod
    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """Split text into chunks based on the chunker's strategy.
        
        This is an abstract method that must be implemented by all child classes.
        
        Args:
            text (str): The text to chunk
            
        Returns:
            List[Dict[str, Any]]: A list of chunk dictionaries with metadata
        """
        pass
    
    def process_play(self, play_text: str, play_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Process a complete play and generate chunks with metadata.
        
        Args:
            play_text (str): The complete text of the play
            play_metadata (Dict[str, Any], optional): Additional metadata about the play
            
        Returns:
            List[Dict[str, Any]]: List of processed chunks with metadata
        """
        # Generate raw chunks
        raw_chunks = self.chunk_text(play_text)
        
        # Add play metadata to each chunk if provided
        if play_metadata:
            for chunk in raw_chunks:
                chunk['play_metadata'] = play_metadata
        
        self.chunks = raw_chunks
        return raw_chunks
    
    def save_chunks(self, output_path: str) -> None:
        """Save processed chunks to a JSON file.
        
        Args:
            output_path (str): Path where the JSON file will be saved
            
        Raises:
            ValueError: If no chunks have been processed
        """
        if not self.chunks:
            raise ValueError("No chunks to save. Process a text first.")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save chunks to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'chunk_type': self.chunk_type,
                'chunks': self.chunks,
                'total_chunks': len(self.chunks)
            }, f, indent=2)
    
    def get_chunk_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific chunk by its index.
        
        Args:
            index (int): The index of the chunk to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: The chunk or None if index is out of range
        """
        if 0 <= index < len(self.chunks):
            return self.chunks[index]
        return None
    
    def get_chunks(self) -> List[Dict[str, Any]]:
        """Get all processed chunks.
        
        Returns:
            List[Dict[str, Any]]: All chunks that have been processed
        """
        return self.chunks
    
    def clear_chunks(self) -> None:
        """Clear all currently stored chunks."""
        self.chunks = []