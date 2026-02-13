import json

import numpy as np
import pandas as pd


def analyze_dataframe(df: pd.DataFrame, return_type: str = "str") -> dict | str:
    """
    Perform statistical analysis on a pandas DataFrame.
    Returns a dictionary of analysis results.
    (Correlation matrix removed)
    """

    analysis = {}

    # 1. Basic Info
    analysis["shape"] = df.shape
    analysis["columns"] = list(df.columns)
    analysis["dtypes"] = df.dtypes.astype(str)

    # 2. Missing Values
    missing_count = df.isnull().sum()
    missing_percent = (missing_count / len(df)) * 100

    analysis["missing"] = pd.DataFrame(
        {"missing_count": missing_count, "missing_percent": missing_percent}
    ).sort_values(by="missing_percent", ascending=False)

    # 3. Numeric Summary
    numeric_cols = df.select_dtypes(include=np.number)

    if not numeric_cols.empty:
        numeric_summary = numeric_cols.describe().T
        numeric_summary["variance"] = numeric_cols.var()
        numeric_summary["skewness"] = numeric_cols.skew()
        numeric_summary["kurtosis"] = numeric_cols.kurt()
        analysis["numeric_summary"] = numeric_summary

    # 4. Categorical Summary
    categorical_cols = df.select_dtypes(include=["object", "category"])

    if not categorical_cols.empty:
        cat_summary = {}
        for col in categorical_cols.columns:
            cat_summary[col] = {
                "unique_count": df[col].nunique(),
                "top_values": df[col].value_counts().head(5).to_dict(),
            }
        analysis["categorical_summary"] = cat_summary

    # 5. Duplicates
    analysis["duplicate_rows"] = df.duplicated().sum()

    if return_type == "str":
        # Convert all DataFrames in analysis to string for better readability
        result = json.dumps(analysis, indent=2)
        return result

    return analysis
