import os

from medcat.cat import CAT

from medcat_den.den import get_default_den

EXAMPLE_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "resources", "example_model_pack.zip")


def main():
    den = get_default_den()
    model = CAT.load_model_pack(EXAMPLE_MODEL_PATH)
    model.config.meta.ontology = ["FAKE ONTO"]
    print("Pushing model to den:", model.config.meta.hash)
    den.push_model(model, "Base FAKE model")


if __name__ == "__main__":
    main()
