"""Duplicate detection module for facility lead records."""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Set
from rapidfuzz import fuzz
import logging

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Multi-tier duplicate detection for facility leads."""
    
    def __init__(
        self,
        exact_match_columns: List[str] = None,
        fuzzy_threshold: float = 0.85,
        llm_client: Optional[Any] = None,
        use_ai_resolution: bool = True
    ):
        """
        Initialize the duplicate detector.
        
        Args:
            exact_match_columns: Columns for exact matching (default: ['phone', 'email'])
            fuzzy_threshold: Similarity threshold for fuzzy matching
            llm_client: LLM client for AI-assisted entity resolution
            use_ai_resolution: Whether to use AI for ambiguous cases
        """
        self.exact_match_columns = exact_match_columns or ['phone', 'email']
        self.fuzzy_threshold = fuzzy_threshold
        self.llm_client = llm_client
        self.use_ai_resolution = use_ai_resolution
        self._cluster_id = 0
    
    def detect_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect and mark duplicates in the DataFrame.
        
        Args:
            df: DataFrame with facility lead data
            
        Returns:
            DataFrame with is_duplicate and duplicate_cluster_id columns
        """
        logger.info(f"Detecting duplicates in {len(df)} records")
        
        result = df.copy()
        
        # Initialize columns
        result['is_duplicate'] = False
        result['duplicate_cluster_id'] = None
        
        # Track seen values for exact matching
        seen_values: Dict[str, Set] = {col: set() for col in self.exact_match_columns}
        
        # Track clusters
        clusters: Dict[str, List[int]] = {}  # cluster_id -> list of indices
        
        # First pass: Exact matching
        for idx, row in result.iterrows():
            matched_cluster = None
            
            for col in self.exact_match_columns:
                value = row.get(col)
                if value and not pd.isna(value):
                    value_str = str(value).strip().lower()
                    
                    if value_str in seen_values[col]:
                        # Found exact match - find which cluster
                        for cluster_id, indices in clusters.items():
                            first_idx = indices[0]
                            first_value = result.loc[first_idx, col]
                            if first_value and str(first_value).strip().lower() == value_str:
                                matched_cluster = cluster_id
                                break
                    else:
                        seen_values[col].add(value_str)
            
            if matched_cluster:
                result.at[idx, 'is_duplicate'] = True
                result.at[idx, 'duplicate_cluster_id'] = matched_cluster
                clusters[matched_cluster].append(idx)
            else:
                # Create new cluster
                self._cluster_id += 1
                cluster_id = f"cluster_{self._cluster_id:06d}"
                result.at[idx, 'duplicate_cluster_id'] = cluster_id
                clusters[cluster_id] = [idx]
        
        logger.info(f"Found {result['is_duplicate'].sum()} exact duplicates")
        
        # Second pass: Fuzzy matching on non-duplicates
        non_duplicate_mask = ~result['is_duplicate']
        non_duplicates = result[non_duplicate_mask].copy()
        
        if len(non_duplicates) > 1:
            fuzzy_matches = self._fuzzy_match_pass(non_duplicates)
            
            for idx1, idx2, score in fuzzy_matches:
                # Mark as duplicate
                cluster_id = result.loc[idx1, 'duplicate_cluster_id']
                result.at[idx2, 'is_duplicate'] = True
                result.at[idx2, 'duplicate_cluster_id'] = cluster_id
                clusters[cluster_id].append(idx2)
        
        logger.info(f"Total duplicates after fuzzy matching: {result['is_duplicate'].sum()}")
        
        return result
    
    def _fuzzy_match_pass(
        self,
        df: pd.DataFrame
    ) -> List[Tuple[int, int, float]]:
        """
        Perform fuzzy matching on company names and addresses.
        
        Args:
            df: DataFrame of non-duplicate records
            
        Returns:
            List of (index1, index2, similarity_score) tuples
        """
        matches = []
        indices = df.index.tolist()
        
        # Pre-normalize for comparison
        companies = df['company'].fillna('').astype(str).str.lower().str.strip().tolist()
        addresses = df['address1'].fillna('').astype(str).str.lower().str.strip().tolist()
        
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                idx1, idx2 = indices[i], indices[j]
                
                # Compare company names
                company_sim = fuzz.ratio(companies[i], companies[j]) / 100
                
                # Compare addresses
                address_sim = fuzz.ratio(addresses[i], addresses[j]) / 100
                
                # Combined scoring
                if company_sim >= self.fuzzy_threshold and address_sim >= 0.70:
                    matches.append((idx1, idx2, (company_sim + address_sim) / 2))
                elif company_sim >= 0.95:  # Very similar names
                    matches.append((idx1, idx2, company_sim))
        
        logger.info(f"Found {len(matches)} fuzzy matches")
        
        # If AI resolution is enabled, process ambiguous matches
        if self.use_ai_resolution and self.llm_client and matches:
            matches = self._ai_resolve_ambiguous(df, matches)
        
        return matches
    
    def _ai_resolve_ambiguous(
        self,
        df: pd.DataFrame,
        matches: List[Tuple[int, int, float]]
    ) -> List[Tuple[int, int, float]]:
        """
        Use LLM to resolve ambiguous duplicate candidates.
        
        Args:
            df: DataFrame with records
            matches: List of candidate matches
            
        Returns:
            Filtered list of confirmed matches
        """
        # Find ambiguous matches (scores between 0.70 and 0.85)
        ambiguous = [(i, j, s) for i, j, s in matches if 0.70 <= s < 0.85]
        
        if not ambiguous:
            return matches
        
        logger.info(f"Sending {len(ambiguous)} ambiguous pairs to AI resolution")
        
        try:
            # Build prompt with record pairs
            prompt = self._build_entity_resolution_prompt(df, ambiguous)
            
            # Call LLM
            response = self.llm_client.complete(prompt)
            
            # Parse response
            confirmed = self._parse_resolution_response(response, ambiguous)
            
            # Combine high-confidence matches with AI-confirmed matches
            high_confidence = [(i, j, s) for i, j, s in matches if s >= 0.85]
            return high_confidence + confirmed
            
        except Exception as e:
            logger.warning(f"AI resolution failed: {e}")
            # Return original matches, filtering out ambiguous ones
            return [(i, j, s) for i, j, s in matches if s >= 0.75]
    
    def _build_entity_resolution_prompt(
        self,
        df: pd.DataFrame,
        pairs: List[Tuple[int, int, float]]
    ) -> str:
        """Build prompt for entity resolution LLM call."""
        pairs_text = []
        for idx, (i, j, score) in enumerate(pairs, 1):
            row1 = df.loc[i]
            row2 = df.loc[j]
            
            pairs_text.append(f"""Pair {idx}:
Record A:
- Company: {row1.get('company', 'N/A')}
- Address: {row1.get('address1', 'N/A')}, {row1.get('city', 'N/A')}, {row1.get('state', 'N/A')}
- Phone: {row1.get('phone', 'N/A')}

Record B:
- Company: {row2.get('company', 'N/A')}
- Address: {row2.get('address1', 'N/A')}, {row2.get('city', 'N/A')}, {row2.get('state', 'N/A')}
- Phone: {row2.get('phone', 'N/A')}

Similarity Score: {score:.2f}
""")
        
        prompt = f"""You are a data deduplication expert for childcare facility records. Determine whether each pair of records refers to the SAME real-world facility or DIFFERENT facilities.

{chr(10).join(pairs_text)}

For each pair, respond with:
- "SAME" if they are the same facility
- "DIFFERENT" if they are different facilities

Consider:
- Similar but not identical names may be the same entity (e.g., "ABC Daycare" vs "ABC Day Care Center")
- Same address but different names could be a renamed facility
- Same phone but different addresses could be a relocated facility
- Different everything is likely different entities

Return your answer as a JSON array:
[
  {{"pair_id": 1, "is_same": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}},
  ...
]"""
        
        return prompt
    
    def _parse_resolution_response(
        self,
        response: str,
        pairs: List[Tuple[int, int, float]]
    ) -> List[Tuple[int, int, float]]:
        """Parse LLM resolution response."""
        import json
        
        confirmed = []
        
        try:
            # Find JSON in response
            json_match = __import__('re').search(r'\[.*\]', response, __import__('re').DOTALL)
            if json_match:
                decisions = json.loads(json_match.group())
                
                for decision in decisions:
                    pair_id = decision.get('pair_id', 0) - 1
                    is_same = decision.get('is_same', False)
                    
                    if is_same and 0 <= pair_id < len(pairs):
                        confirmed.append(pairs[pair_id])
        
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM resolution response")
        
        return confirmed
    
    def get_duplicate_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get summary statistics for duplicates.
        
        Args:
            df: DataFrame with duplicate flags
            
        Returns:
            Dictionary with duplicate summary
        """
        if 'is_duplicate' not in df.columns:
            return {"error": "DataFrame does not have duplicate flags"}
        
        total = len(df)
        duplicates = df['is_duplicate'].sum()
        unique = total - duplicates
        
        # Count clusters
        if 'duplicate_cluster_id' in df.columns:
            clusters = df['duplicate_cluster_id'].nunique()
            avg_cluster_size = total / clusters if clusters > 0 else 0
        else:
            clusters = 0
            avg_cluster_size = 0
        
        return {
            "total_records": total,
            "unique_records": int(unique),
            "duplicate_records": int(duplicates),
            "duplicate_rate": round(duplicates / total * 100, 2) if total > 0 else 0,
            "clusters": int(clusters),
            "average_cluster_size": round(avg_cluster_size, 2),
        }
