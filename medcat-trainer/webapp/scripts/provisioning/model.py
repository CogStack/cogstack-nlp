"""
Pydantic models for the provisioning YAML config.

The user provides a YAML file that describes which projects to load on startup.
Nested structure (modelPack, dataset, project) matches where fields are used
when POSTing to the API (modelpacks/, create-dataset/, project-annotate-entities/).

Python fields are snake_case; YAML keys are camelCase via alias_generator.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

_common_config = ConfigDict(
    alias_generator=to_camel,
    validate_by_name=True,
    validate_by_alias=True,
)


class ModelPackSpec(BaseModel):
    """Model pack to upload to modelpacks/."""

    name: str = Field(description="Display name for the model pack")
    url: str = Field(description="URL of the model pack .zip to download")


class DatasetSpec(BaseModel):
    """Dataset to upload via create-dataset/ (name, description, data from url)."""

    name: str = Field(description="Display name for the dataset")
    url: str = Field(description="URL of the dataset CSV to download")
    description: str = Field(description="Dataset description")


class ProjectSpec(BaseModel):
    """Project to create via project-annotate-entities/."""

    model_config = _common_config

    name: str = Field(description="Name of the created project")
    description: str = Field(description="Project description")
    annotation_guideline_link: str = Field(description="URL to annotation guidelines")
    use_model_service: bool = Field(
        default=False,
        description="Use remote MedCAT service API for document processing instead of local models.",
    )
    model_service_url: str | None = Field(
        default=None,
        description="URL of the remote MedCAT service API (e.g. http://medcat-service:8000). Required when use_model_service is True.",
    )


class ProvisioningProjectSpec(BaseModel):
    """
    Spec for one example project to be loaded on startup.
    Either provide model_pack (project uses uploaded model), or set project.use_model_service=True
    and project.model_service_url (remote MedCAT service API for document processing).
    """

    model_config = _common_config

    model_pack: ModelPackSpec | None = Field(
        default=None,
        description="Model pack to upload (name + url). Required when project.use_model_service is False.",
    )
    dataset: DatasetSpec = Field()
    project: ProjectSpec = Field()

    @model_validator(mode="after")
    def exactly_one_model_source(self):
        if self.project.use_model_service:
            if not self.project.model_service_url or not self.project.model_service_url.strip():
                raise ValueError("model_service_url is required when use_model_service is True")
            if self.model_pack is not None:
                raise ValueError("Do not set model_pack when use_model_service is True")
        else:
            if self.model_pack is None:
                raise ValueError("model_pack is required when use_model_service is False")
        return self


class ProvisioningConfig(BaseModel):
    """Root config: list of example projects to load on startup."""

    model_config = _common_config

    projects: list[ProvisioningProjectSpec] = Field(
        description="List of example project specs to load",
    )
