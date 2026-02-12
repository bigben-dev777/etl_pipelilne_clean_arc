"""AI-powered facility type classification."""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
import logging

from src.transform.ai.llm_client import LLMClient

logger = logging.getLogger(__name__)


class FacilityClassifier:
    """
    Classify facility types using LLM with rule-based fallback.
    """
    
    # Standard facility type categories
    CATEGORIES = [
        "Child Care Center",
        "Family Child Care",
        "Group Home",
        "School Age Program",
        "Head Start",
        "Preschool",
        "Residential",
        "Other"
    ]
    
    # Rule-based keyword mappings for fallback
    KEYWORD_MAPPINGS = {
        "Child Care Center": [
            "center", "daycare center", "day care center", "learning center",
            "child care", "childcare", "academy", "preschool", "pre-school"
        ],
        "Family Child Care": [
            "family care", "family child care", "home daycare", "home care",
            "in-home", "family home", "residential care"
        ],
        "Group Home": [
            "group home", "group care", "group childcare"
        ],
        "School Age Program": [
            "school age", "after school", "before school", "school program"
        ],
        "Head Start": [
            "head start", "early head start"
        ],
        "Preschool": [
            "preschool", "pre-school", "pre school", "pre-k", "pre k"
        ],
        "Residential": [
            "residential", "group home", "shelter", "foster"
        ],
    }
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        use_llm: bool = True,
        batch_size: int = 20
    ):
        """
        Initialize the facility classifier.
        
        Args:
            llm_client: LLM client for classification
            use_llm: Whether to use LLM (vs rule-based only)
            batch_size: Number of facilities to classify per LLM call
        """
        self.llm_client = llm_client
        self.use_llm = use_llm
        self.batch_size = batch_size
        self._classification_cache: Dict[str, Tuple[str, float]] = {}
    
    def classify(
        self,
        facility_descriptions: List[str],
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Classify a list of facility descriptions.
        
        Args:
            facility_descriptions: List of facility type descriptions
            use_cache: Whether to use caching
            
        Returns:
            List of classification results
        """
        if not facility_descriptions:
            return []
        
        results = []
        to_classify = []
        to_classify_indices = []
        
        # Check cache first
        for idx, desc in enumerate(facility_descriptions):
            if not desc or not isinstance(desc, str):
                results.append({
                    "original": desc,
                    "category": "Other",
                    "confidence": 0.0,
                    "source": "invalid_input"
                })
                continue
            
            normalized = desc.lower().strip()
            
            if use_cache and normalized in self._classification_cache:
                category, confidence = self._classification_cache[normalized]
                results.append({
                    "original": desc,
                    "category": category,
                    "confidence": confidence,
                    "source": "cache"
                })
            else:
                to_classify.append(desc)
                to_classify_indices.append(idx)
                results.append(None)  # Placeholder
        
        # Classify remaining items
        if to_classify:
            if self.use_llm and self.llm_client:
                classified = self._classify_with_llm(to_classify)
            else:
                classified = self._classify_with_rules(to_classify)
            
            # Fill in results and cache
            for idx, desc, result in zip(to_classify_indices, to_classify, classified):
                results[idx] = result
                
                if use_cache:
                    normalized = desc.lower().strip()
                    self._classification_cache[normalized] = (
                        result["category"],
                        result["confidence"]
                    )
        
        return results
    
    def classify_single(
        self,
        facility_description: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Classify a single facility description.
        
        Args:
            facility_description: Facility type description
            use_cache: Whether to use caching
            
        Returns:
            Classification result
        """
        results = self.classify([facility_description], use_cache)
        return results[0] if results else {"category": "Other", "confidence": 0.0}
    
    def _classify_with_llm(
        self,
        descriptions: List[str]
    ) -> List[Dict[str, Any]]:
        """Classify using LLM in batches."""
        results = []
        
        # Process in batches
        for i in range(0, len(descriptions), self.batch_size):
            batch = descriptions[i:i + self.batch_size]
            batch_results = self._classify_batch(batch)
            results.extend(batch_results)
        
        return results
    
    def _classify_batch(self, batch: List[str]) -> List[Dict[str, Any]]:
        """Classify a batch of descriptions."""
        # Build prompt
        numbered = [f"{i+1}. {desc}" for i, desc in enumerate(batch)]
        
        prompt = f"""You are a childcare facility classification expert. Classify each facility description into exactly ONE of the following standardized categories:

CATEGORIES:
- "Child Care Center" — Licensed center-based daycare facilities
- "Family Child Care" — Home-based childcare (small family or large family)
- "Group Home" — Group childcare home
- "School Age Program" — Before/after school care programs
- "Head Start" — Federally funded early childhood programs
- "Preschool" — Educational programs for ages 3-5
- "Residential" — Residential care facilities for children
- "Other" — Does not fit any above category

INPUT FACILITY DESCRIPTIONS (one per line, numbered):
{chr(10).join(numbered)}

Return a JSON array with one object per input:
[
  {{"index": 1, "original": "...", "category": "...", "confidence": 0.0-1.0}},
  ...
]

Rules:
- Use ONLY the categories listed above
- If ambiguous, choose the closest match and lower the confidence score
- "confidence" should reflect your certainty (1.0 = certain, 0.5 = uncertain)"""
        
        try:
            response = self.llm_client.complete(prompt)
            
            # Parse response
            classifications = self._parse_llm_response(response, batch)
            
            return classifications
            
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, falling back to rules")
            return self._classify_with_rules(batch)
    
    def _parse_llm_response(
        self,
        response: str,
        original_descriptions: List[str]
    ) -> List[Dict[str, Any]]:
        """Parse LLM classification response."""
        results = []
        
        try:
            # Extract JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                for item in data:
                    idx = item.get('index', 1) - 1
                    if 0 <= idx < len(original_descriptions):
                        results.append({
                            "original": original_descriptions[idx],
                            "category": item.get('category', 'Other'),
                            "confidence": item.get('confidence', 0.5),
                            "source": "llm"
                        })
        
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM classification response")
        
        # Fill in any missing results
        while len(results) < len(original_descriptions):
            idx = len(results)
            rule_result = self._classify_single_with_rules(original_descriptions[idx])
            results.append(rule_result)
        
        return results
    
    def _classify_with_rules(
        self,
        descriptions: List[str]
    ) -> List[Dict[str, Any]]:
        """Classify using rule-based keyword matching."""
        return [self._classify_single_with_rules(desc) for desc in descriptions]
    
    def _classify_single_with_rules(self, description: str) -> Dict[str, Any]:
        """Classify a single description using rules."""
        if not description:
            return {"original": description, "category": "Other", "confidence": 0.0, "source": "rules"}
        
        desc_lower = description.lower()
        
        # Check each category's keywords
        for category, keywords in self.KEYWORD_MAPPINGS.items():
            for keyword in keywords:
                if keyword in desc_lower:
                    return {
                        "original": description,
                        "category": category,
                        "confidence": 0.7,
                        "source": "rules"
                    }
        
        # Default to Other
        return {
            "original": description,
            "category": "Other",
            "confidence": 0.5,
            "source": "rules"
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get classification cache statistics."""
        return {
            "cache_size": len(self._classification_cache),
            "categories_in_cache": list(set(cat for cat, _ in self._classification_cache.values()))
        }
