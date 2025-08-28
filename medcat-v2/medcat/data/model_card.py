from typing import Any
from typing_extensions import TypedDict


CDBInfo = TypedDict(
    "CDBInfo", {
        "Number of concepts": int,
        "Number of names": int,
        "Number of concepts that received training": int,
        "Number of seen training examples in total": int,
        "Average training examples per concept": float,
        "Unsupervised training history": list[dict[str, Any]],
        "Supervised training history": list[dict[str, Any]],
    }
)


ModelCard = TypedDict(
    "ModelCard", {
        "Model ID": str,
        "Last Modified On": str,
        "History (from least to most recent)": list[str],
        'Description': str,
        'Source Ontology': list[str],
        'Location': str,
        'MetaCAT models': list[dict],
        'Basic CDB Stats': CDBInfo,
        'Performance': dict[str, Any],
        ('Important Parameters '
         '(Partial view, all available in cat.config)'): dict[str, Any],
        'MedCAT Version': str,
    }
)
