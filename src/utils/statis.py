import json

import numpy as np
import pandas as pd


def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(x) for x in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    else:
        return obj


def analyze_dataframe(df: pd.DataFrame, return_type: str = "str") -> dict | str:
    analysis = {}
    try:
        analysis["shape"] = df.shape
        analysis["columns"] = list(df.columns)
        analysis["dtypes"] = df.dtypes.astype(str)

        missing_count = df.isnull().sum()
        missing_percent = (missing_count / len(df)) * 100
        analysis["missing"] = pd.DataFrame(
            {"missing_count": missing_count, "missing_percent": missing_percent}
        ).sort_values(by="missing_percent", ascending=False)

        numeric_cols = df.select_dtypes(include=np.number)
        if not numeric_cols.empty:
            numeric_summary = numeric_cols.describe().T
            numeric_summary["variance"] = numeric_cols.var()
            numeric_summary["skewness"] = numeric_cols.skew()
            numeric_summary["kurtosis"] = numeric_cols.kurt()
            analysis["numeric_summary"] = numeric_summary

        categorical_cols = df.select_dtypes(include=["object", "category"])
        if not categorical_cols.empty:
            cat_summary = {}
            for col in categorical_cols.columns:
                cat_summary[col] = {
                    "unique_count": df[col].nunique(),
                    "top_values": df[col].value_counts().head(5).to_dict(),
                }
            analysis["categorical_summary"] = cat_summary

        analysis["duplicate_rows"] = df.duplicated().sum()

        if return_type == "str":
            analysis_serializable = {}
            for k, v in analysis.items():
                if isinstance(v, pd.DataFrame):
                    analysis_serializable[k] = convert_numpy(
                        v.to_dict(orient="records")
                    )
                elif isinstance(v, pd.Series):
                    analysis_serializable[k] = convert_numpy(v.to_dict())
                else:
                    analysis_serializable[k] = convert_numpy(v)
            return json.dumps(analysis_serializable, indent=2)

        return analysis

    except Exception as e:
        raise RuntimeError(f"DataFrame analysis failed: {e}")
