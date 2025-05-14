# In types.py
from dataclasses import dataclass
from typing import Dict, List, Union

ReferenceDict = Dict[str, Union[str, int, List[str], List[int]]]

@dataclass
class CandidateQuote:
    text: str
    reference: ReferenceDict
    score: float
