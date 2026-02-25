import os
import json

from medcat_den import base


from . import V1_MODEL_PATH

import pytest


@pytest.fixture
def v1_model_card():
    model_card_path = os.path.join(
        V1_MODEL_PATH.removesuffix(".zip"), "model_card.json")
    # NOTE: for some reason, this doesn't exist at this point
    from medcat.cat import CAT
    CAT.attempt_unpack(V1_MODEL_PATH)
    with open(model_card_path) as f:
        return json.load(f)


def test_can_get_model_card(v1_model_card):
    model_info = base.ModelInfo(model_id=v1_model_card["Model ID"],
                                model_card=v1_model_card,
                                base_model=None)
    assert isinstance(model_info, base.ModelInfo)
