from modules.rag.embeddings import EmbeddingGenerator
from modules.rag.vector_store import VectorStore
from modules.chunking.phrase_chunker import PhraseChunker
from modules.chunking.fragment_chunker import FragmentChunker
from modules.utils.logger import CustomLogger

class ShakespeareSearchEngine:
    def __init__(self, logger=None):
        self.logger = logger or CustomLogger("SearchEngine")
        self.embedder = EmbeddingGenerator(logger=self.logger)
        self.vector_stores = {
            "lines": VectorStore(collection_name="lines", logger=self.logger),
            "phrases": VectorStore(collection_name="phrases", logger=self.logger),
            "fragments": VectorStore(collection_name="fragments", logger=self.logger),
        }
        self.phrase_chunker = PhraseChunker(logger=self.logger)
        self.fragment_chunker = FragmentChunker(logger=self.logger)

    def search_line(self, modern_line: str, top_k=3):
        result = {
            "original_line": modern_line,
            "search_chunks": {
                "line": [],
                "phrases": [],
                "fragments": []
            }
        }

        # 1. Line-level embedding
        line_embedding = self.embedder.embed_texts([modern_line])[0]
        result["search_chunks"]["line"] = self.vector_stores["lines"].collection.query(
            query_embeddings=[line_embedding], n_results=top_k, include=["documents", "metadatas", "distances"]
        )

        # 2. Phrase-level chunking & search
        line_dict = {"text": modern_line, "chunk_id": "input_line"}
        phrase_chunks = self.phrase_chunker.chunk_from_line_chunks([line_dict])
        for chunk in phrase_chunks:
            emb = self.embedder.embed_texts([chunk["text"]])[0]
            search_result = self.vector_stores["phrases"].collection.query(
                query_embeddings=[emb], n_results=top_k, include=["documents", "metadatas", "distances"]
            )
            result["search_chunks"]["phrases"].append(search_result)

        # 3. Fragment-level chunking & search
        fragment_chunks = self.fragment_chunker.chunk_from_line_chunks([line_dict])
        for chunk in fragment_chunks:
            emb = self.embedder.embed_texts([chunk["text"]])[0]
            search_result = self.vector_stores["fragments"].collection.query(
                query_embeddings=[emb], n_results=top_k, include=["documents", "metadatas", "distances"]
            )
            result["search_chunks"]["fragments"].append(search_result)

        return result
    
    def hybrid_search(self, modern_line: str, top_k=5):
        """
        Perform a hybrid search combining vector similarity with keyword matching.
        This provides more diverse results when standard vector search yields insufficient options.
        
        Args:
            modern_line: The modern text line to find Shakespeare quotes for
            top_k: Number of results to return per search method
            
        Returns:
            Dictionary with search results from different approaches
        """
        self.logger.info(f"Performing hybrid search for: '{modern_line}'")
        
        # Initialize a result structure
        result = {
            "original_line": modern_line,
            "search_method": "hybrid",
            "search_chunks": {
                "line": [],
                "phrases": [],
                "fragments": []
            }
        }
        
        try:
            # First get regular vector search results
            vector_results = self.search_line(modern_line, top_k)
            
            # Extract the vector search results for each level - with error handling
            if "search_chunks" in vector_results:
                search_chunks = vector_results["search_chunks"]
                
                # Handle line results
                if "line" in search_chunks:
                    result["search_chunks"]["line"] = search_chunks["line"]
                
                # Handle phrases results
                if "phrases" in search_chunks and isinstance(search_chunks["phrases"], list):
                    result["search_chunks"]["phrases"] = search_chunks["phrases"]
                
                # Handle fragments results
                if "fragments" in search_chunks and isinstance(search_chunks["fragments"], list):
                    result["search_chunks"]["fragments"] = search_chunks["fragments"]
            
            # Now add keyword-based search results
            try:
                import re
                from collections import Counter
                
                # Extract significant words from the modern line
                words = re.findall(r'\b\w{3,}\b', modern_line.lower())
                
                # Define stopwords to filter out common words
                stopwords = {
                    'the', 'and', 'that', 'have', 'for', 'not', 'with', 'you', 'this', 'but',
                    'his', 'from', 'they', 'will', 'would', 'what', 'all', 'were', 'when',
                    'there', 'their', 'your', 'been', 'one', 'who', 'very', 'had', 'was', 'are',
                    'she', 'her', 'him', 'has', 'our', 'them', 'its', 'about', 'can', 'out'
                }
                
                # Filter out stopwords and get the most relevant keywords
                keywords = [w for w in words if w not in stopwords]
                
                # Take the 3 most common keywords (if available)
                if keywords:
                    keyword_freq = Counter(keywords)
                    top_keywords = [kw for kw, _ in keyword_freq.most_common(3)]
                    
                    self.logger.info(f"Extracted keywords for search: {top_keywords}")
                    
                    # For each keyword, search each collection
                    for keyword in top_keywords:
                        try:
                            keyword_embedding = self.embedder.embed_texts([keyword])[0]
                            
                            for level in ["line", "phrases", "fragments"]:
                                try:
                                    collection = self.vector_stores[level].collection
                                    
                                    # Search using the keyword embedding
                                    keyword_results = collection.query(
                                        query_embeddings=[keyword_embedding],
                                        n_results=3,  # Fewer per keyword
                                        include=["documents", "metadatas", "distances"]
                                    )
                                    
                                    # Add these results to our result dictionary
                                    if level == "line":
                                        # Line results can be directly merged
                                        result["search_chunks"][level] = keyword_results
                                    else:
                                        # Phrases and fragments results must be appended
                                        result["search_chunks"][level].append(keyword_results)
                                except Exception as e:
                                    self.logger.warning(f"Error searching {level} for keyword '{keyword}': {e}")
                        except Exception as e:
                            self.logger.warning(f"Error processing keyword '{keyword}': {e}")
                
            except Exception as e:
                self.logger.warning(f"Error in keyword-based search: {e}")
            
            # Check if we found any results
            total_line_results = len(result["search_chunks"]["line"].get("documents", []) 
                                if isinstance(result["search_chunks"]["line"], dict) else [])
            total_phrase_results = sum(len(r.get("documents", [])) 
                                    for r in result["search_chunks"]["phrases"] 
                                    if isinstance(r, dict))
            total_fragment_results = sum(len(r.get("documents", [])) 
                                    for r in result["search_chunks"]["fragments"] 
                                    if isinstance(r, dict))
            
            self.logger.info(f"Hybrid search results: {total_line_results} lines, "
                            f"{total_phrase_results} phrases, "
                            f"{total_fragment_results} fragments")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in hybrid search: {e}")
            return result