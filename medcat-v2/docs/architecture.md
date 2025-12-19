# MedCAT Architecture & Extensibility

## Overview

MedCAT is built on a flexible, registry-based architecture that allows you to customize and extend every part of the processing pipeline. This document explains the core concepts and how to create your own components.

## Core Concepts

### Components
**Components** are the building blocks of MedCAT. They fall into two categories:

- **Core components**: Essential components that provide entity recognition and linking
  - **NER** (Named Entity Recognition): Identifies medical entities in text
  - **Linker**: Links identified entities to concepts in your medical database (CDB)
  - Also: Token normalizers and taggers

- **Addon components**: Optional components that add functionality beyond NER and linking
  - **MetaCAT**: Adds meta-annotation (e.g., experiencer, negation, temporality)
  - **RelCAT**: Extracts relationships between entities
  - Custom addons for domain-specific tasks

### Registry System
All components are registered in a central registry. This means you can:
- Swap out default implementations with your own
- Choose between multiple NER or linking strategies
- Add custom processing stages to the pipeline

### Plugins
**Plugins** are external Python packages that provide new component implementations or other functionality. They integrate with MedCAT through Python entry points, allowing automatic discovery and registration without modifying MedCAT's core code.

---

## Working with Core Components

### Registering Core Components

Core components must implement `AbstractEntityProvidingComponent` for NER/linking functionality.

**Standard registration:**
```python
from medcat.components.types import register_core_component, CoreComponentType

register_core_component(
    CoreComponentType.ner,  # or CoreComponentType.linking
    "my_custom_ner",
    my_ner_initializer_function
)
```

**Lazy registration** (recommended for plugins):
```python
from medcat.components.types import lazy_register_core_component, CoreComponentType

lazy_register_core_component(
    CoreComponentType.ner,
    "mypackage.ner.module",
    "MyNERClass.create_new_component"
)
```

Lazy registration defers importing the component until it's actually used, improving startup time and avoiding unnecessary dependencies.

### Using Core Components

Set the component name in your configuration:
```python
# For NER
config.components.ner.comp_name = "my_custom_ner"

# For linking
config.components.linking.comp_name = "my_custom_linker"

# If modifying an existing model, recreate the pipeline
cat._recreate_pipe()
```

### Implementing a Core Component

Extend `AbstractEntityProvidingComponent` and implement these required methods:
```python
from medcat.components.types import AbstractEntityProvidingComponent, CoreComponentType
from medcat.document import MutableDocument, MutableEntity
from medcat.config import ComponentConfig
from medcat.tokenizing import BaseTokenizer
from medcat.cdb import CDB
from medcat.vocab import Vocab

class MyCustomNER(AbstractEntityProvidingComponent):
    
    @property
    def name(self) -> str:
        """The name of the component."""
        return "my_custom_ner"
    
    def get_type(self) -> CoreComponentType:
        """Returns the component type (NER or LINKING)."""
        return CoreComponentType.NER
    
    def predict_entities(
        self, 
        doc: MutableDocument,
        ents: list[MutableEntity] | None = None
    ) -> list[MutableEntity]:
        """
        Main prediction method.
        
        Args:
            doc: The document to process
            ents: Existing entities (for linkers; None for NER)
            
        Returns:
            List of predicted entities
        """
        # Your entity prediction logic here
        pass
    
    @classmethod
    def create_new_component(
        cls,
        cnf: ComponentConfig,
        tokenizer: BaseTokenizer,
        cdb: CDB,
        vocab: Vocab,
        model_load_path: str | None
    ) -> 'MyCustomNER':
        """
        Factory method for creating instances.
        
        This is called by MedCAT when initializing the component.
        """
        return cls(cnf, tokenizer, cdb, vocab, model_load_path)
```

---

## Working with Addon Components

### Registering Addons
```python
from medcat.components.addons.addons import register_addon

register_addon("my_custom_addon", my_addon_initializer)
```

**Note:** Lazy registration for addons is planned for a future release.

### Using Addons

Add addon before creating a model pack creation:
```python
class MyAddonConfig(ComponentConfig):
    pass
cnf = MyAddonConfig()
# Append addon config to the addons list
config.components.addons.append(cnf)

# Create model pack
cat = CAT(cdb, vocab, config)
cat._recreate_pipe()
```

Add the addon configuration to an existing model:
```python
cat: CAT  # model
my_addon: MyAddon  # addon
# Add the addon
# This will automatically make necessary config changes
cat.add_addon(my_addon)
```


### Implementing an Addon

Extend `AddonComponent` and implement these required methods:
```python
from medcat.components.addons.addons import AddonComponent
from medcat.document import MutableDocument, MutableEntity
from medcat.config import ComponentConfig
from medcat.tokenizing import BaseTokenizer
from medcat.cdb import CDB
from medcat.vocab import Vocab
from typing import Any, Optional

class MyCustomAddon(AddonComponent):
    
    @property
    def full_name(self) -> Optional[str]:
        """Name with the component type (e.g., 'ner', 'linking', 'meta')."""
        return f"{self.addon_type()}.{self.name}"
    
    @property
    def name(self) -> str:
        """The name of the component."""
        return "my_custom_addon"
    
    def addon_type(self) -> str:
        """The type/category of this addon (e.g., 'meta', 'rel')."""
        return "custom"
    
    def get_output_key_val(
        self, 
        ent: MutableEntity
    ) -> tuple[str, dict[str, Any]]:
        """
        Defines how this addon's output is stored in entities.
        
        Returns:
            Tuple of (key, value_dict) to be added to entity metadata
        """
        return ("my_addon_output", {"result": "..."})
    
    def __call__(self, doc: MutableDocument) -> MutableDocument:
        """
        Process the document and its entities.
        
        Args:
            doc: Document with entities from NER/linking
            
        Returns:
            Modified document with addon annotations
        """
        # Your addon logic here
        for entity in doc.entities:
            # Process entity
            key, value = self.get_output_key_val(entity)
            entity.metadata[key] = value
        
        return doc
    
    @classmethod
    def create_new_component(
        cls,
        cnf: ComponentConfig,
        tokenizer: BaseTokenizer,
        cdb: CDB,
        vocab: Vocab,
        model_load_path: Optional[str]
    ) -> 'MyCustomAddon':
        """Factory method for creating instances."""
        return cls(cnf, tokenizer, cdb, vocab, model_load_path)
```

---

## Working with Tokenizers

Tokenizers are also pluggable components. The registry system extends to tokenization strategies as well.

### Registering a Tokenizer
```python
from medcat.tokenizing.tokenizers import register_tokenizer
from medcat.tokenizing import BaseTokenizer

register_tokenizer("my_custom_tokenizer", MyTokenizerClass)
```

**Note:** Lazy registration for tokenizers is planned for a future release.

### Using a Custom Tokenizer
```python
config.general.nlp.provider = "my_custom_tokenizer"
```

---

## Creating Plugins

Plugins are external Python packages that provide MedCAT components. They're the recommended way to distribute custom implementations.

### Plugin Structure

A MedCAT plugin is a Python package that:
1. Registers its components (preferably using lazy registration)
2. Declares itself via entry points in `pyproject.toml`

### Entry Point Configuration

In your plugin's `pyproject.toml`:
```toml
[project.entry-points."medcat.plugins"]
my_plugin = "my_plugin_package.registration"
```

### Registration Module

Create a registration module (e.g., `my_plugin_package/registration.py`):
```python
from medcat.components.types import lazy_register_core_component, CoreComponentType
from medcat.components.addons.addons import register_addon

def register():
    """Called automatically when MedCAT discovers this plugin."""
    
    # Register a custom NER component - lazy registration recommended
    lazy_register_core_component(
        CoreComponentType.NER,
        "my_plugin_package.ner",
        "MyNER.create_new_component"
    )
    
    # Register an addon
    register_addon(
        "my_plugin_addon",
        MyADdonClass
    )

# Automatically register when imported
register()
```

### Plugin Best Practices

1. **Use lazy registration** - Improves startup time and avoids import errors for unused components
2. **Namespace your component names** - Use prefixes like `"myplugin_ner"` to avoid conflicts
3. **Document requirements** - Specify any additional dependencies your plugin needs
4. **Provide examples** - Show users how to configure and use your components
5. **Version compatibility** - Clearly specify which MedCAT versions your plugin supports

### Example Plugin Package
```
my_medcat_plugin/
├── pyproject.toml
├── README.md
├── my_plugin_package/
│   ├── __init__.py
│   ├── registration.py  # Entry point module
│   ├── ner.py           # Custom NER implementation
│   └── addons/
│       ├── __init__.py
│       └── my_addon.py  # Custom addon implementation
└── tests/
    └── ...
```

---

## Pipeline Lifecycle

Understanding when components are loaded and how they interact:

1. **Configuration** - Set component names and addon configs
2. **Discovery** - MedCAT discovers plugins via entry points
3. **Registration** - Plugins register their components in the registry
4. **Initialization** - Components are instantiated via `create_new_component()`
5. **Pipeline creation** - Components are assembled into the processing pipeline
6. **Execution** - Documents flow through: Tokenizer → NER → Linker → Addons

### Modifying Existing Models

When changing components on an already-initialized CAT instance:
```python
# Modify configuration
cat.config.components.ner.comp_name = "new_ner"

# Recreate the pipeline to apply changes
cat._recreate_pipe()
```

This is **not** required when creating a new model pack from scratch.

---

## Advanced Topics

### Component Dependencies

Components can depend on each other:
- **Linkers** receive entities from NER as input
- **Addons** receive fully annotated documents from NER + Linker
- All components receive the tokenizer, CDB, and vocab

### Configuration Schema

Each component type can define its own configuration schema within `ComponentConfig`. Use this to make your components configurable:
```python
class MyNER(AbstractEntityProvidingComponent):
    def __init__(self, cnf: ComponentConfig, ...):
        self.confidence_threshold = cnf.custom_config.get(
            "confidence_threshold", 
            0.7
        )
```

### Error Handling

Components should handle errors gracefully:
- Return empty lists rather than raising exceptions when no entities are found
- Log warnings for configuration issues
- Validate inputs in `create_new_component()`

---


## Examples

### Example 1: Using a Plugin-Provided NER
```python
# Install the plugin
# pip install medcat-gliner-plugin

from medcat.cat import CAT

# Load model
cat = CAT.load_model_pack("model_pack_path")

# Switch to GLiNER (provided by plugin)
cat.config.components.ner.comp_name = "gliner"
cat._recreate_pipe()

# Use as normal
doc = cat("Patient presents with chest pain...")
```

### Example 2: Creating a Custom Addon
```python
from medcat.components.addons.addons import AddonComponent, register_addon

class SentimentAddon(AddonComponent):
    MY_ADDON_PATH = "MY_ADDON_DAT"

    def __init__(self, cnf, tokenizer) -> None:
        self.cnf = cnf
        self.tokenizer = tokenizer
        # register addon path on the entity
        self.tokenizer.get_entity_class().register_addon_path(
            self.MY_ADDON_PATH, def_val=None, force=True)

    @property
    def name(self):
        return "sentiment"
    
    def addon_type(self):
        return "meta"
    
    def __call__(self, doc):
        for ent in doc.entities:
            # Simple sentiment logic
            sentiment = self.analyze_sentiment(ent.text)
            # set the addon data on the entiy
            ent.set_addon_data(self.MY_ADDON_PATH, sentiment)
        return doc
    
    def get_output_key_val(self, ent):
        # Retrieve the addon data from the entity
        # NOTE: The first string is the key in the overall output dict
        return self.MY_ADDON_PATH, ent.get_addon_data(self.MY_ADDON_PATH)
    
    def analyze_sentiment(self, text):
        # Your sentiment analysis logic
        return 0.5
    
    @classmethod
    def create_new_component(cls, cnf, tokenizer, cdb, vocab, model_load_path):
        return cls(cnf, tokenizer)

# Register it
register_addon("sentiment", SentimentAddon.create_new_component)

# Use it
cat.config.components.addons.append({"name": "sentiment"})
cat._recreate_pipe()
```

---

## Further Resources

- **API Reference**: [Docs](https://docs.cogstack.org/projects/nlp/en/latest/)
- **Example Plugins**: Upcoming
- **Community Plugins**: None yet
- **Support**: [discourse](https://discourse.cogstack.org/)