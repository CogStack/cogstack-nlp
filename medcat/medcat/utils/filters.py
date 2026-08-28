from typing import Optional
from contextlib import nullcontext

from medcat.config.config import LinkingFilters
from medcat.data.mctexport import MedCATTrainerExportProject
from medcat.utils.config_utils import temp_changed_config


def project_filters(filters: LinkingFilters,
                    project: MedCATTrainerExportProject,
                    extra_cui_filter: Optional[set[str]],
                    use_project_filters: bool):
    """Context manager with per project filters based on a trainer export.

    Args:
        filters (LinkingFilters): The current config.
        project (MedCATTrainerExportProject): The trainer export.
        extra_cui_filter (Optional[set[str]]): Extra cui filters.
        use_project_filters (bool): Whether to use project filters.
    """
    if extra_cui_filter is not None and not use_project_filters:
        return temp_changed_config(filters, 'cuis', extra_cui_filter)
    if use_project_filters:
        cuis = project.get('cuis', None)
        if cuis is None or not cuis:
            return nullcontext()
        return temp_changed_config(filters, 'cuis', set(cuis.split(",")))
    return temp_changed_config(filters, 'cuis', set())
