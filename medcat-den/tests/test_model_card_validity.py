from medcat_den.base import ModelInfo


MODEL_CARD_NO_NEW_KEYS = {
    "Model ID": "0a1b2c3d4e",
    "Source Ontology": [],
    "Last Modified On": "2025-01-01",
    "History (from least to most recent)": ["aa1122ee44"],
    "Description": "Test model",
    "Location": "test",
    "MetaCAT models": [],
    "Basic CDB Stats": {
        "Number of concepts": 0,
        "Number of names": 0,
        "Number of concepts that received training": 0,
        "Number of seen training examples in total": 0,
        "Average training examples per concept": 0,
        "Unsupervised training history": [],
        "Supervised training history": [],
    },
    "Performance": {},
    "Important Parameters (Partial view, all available in cat.config)": {},
    "MedCAT Version": "2.0.0",
}

NEW_KV = {
    "Pipeline Description": {
        "core": {}, "addons": []
    },
    "Required Plugins": []
}


MODEL_CARD_WITH_NEW_KEYS = {
    **MODEL_CARD_NO_NEW_KEYS,
    **NEW_KV
}


def test_validates_with_old_format():
    model = ModelInfo(
        model_id="test_id",
        model_card=MODEL_CARD_NO_NEW_KEYS,
            base_model=None,
        model_name="test_model",
        model_num=1,
    )
    assert isinstance(model, ModelInfo)


def test_validates_with_new_format():
    model = ModelInfo(
        model_id="test_id",
        model_card=MODEL_CARD_WITH_NEW_KEYS,
            base_model=None,
        model_name="test_model",
        model_num=1,
    )
    assert isinstance(model, ModelInfo)


def test_new_format_keeps_values():
    model = ModelInfo(
        model_id="test_id",
        model_card=MODEL_CARD_WITH_NEW_KEYS,
            base_model=None,
        model_name="test_model",
        model_num=1,
    )
    mc = model.model_card
    for key, exp_value in NEW_KV.items():
        assert exp_value == mc[key]
