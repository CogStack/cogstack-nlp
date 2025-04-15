from typing import Any
from typing_extensions import TypedDict


ModelCard = TypedDict(
    "ModelCard", {
        "Model ID": str,
        "Last Modified On": str,
        "History (from least to most recent)": list[str],
        'Description': str,
        'Source Ontology': list[str],
        'Location': str,
        'MetaCAT models': list[str],
        'Basic CDB Stats': dict[str, Any],
        'Performance': dict[str, Any],
        ('Important Parameters '
         '(Partial view, all available in cat.config)'): dict[str, Any],
        'MedCAT Version': str,
    }
)
