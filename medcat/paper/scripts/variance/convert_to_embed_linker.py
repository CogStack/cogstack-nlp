import os

from medcat.cat import CAT
from medcat.components.types import CoreComponentType
from medcat.config.config import EmbeddingLinking
from medcat.components.linking.embedding_linker import (
    Linker as ELinker)


def convert(cat: CAT):
    cmp_cnf = cat.config.components
    cmp_cnf.linking = EmbeddingLinking()
    # NOTE: should fix on the lib side
    cmp_cnf.linking.comp_name = "medcat2_embedding_linker"
    # need to recreate and create embeddings
    cat._recreate_pipe()
    linker: ELinker = cat.pipe.get_component(CoreComponentType.linking)
    print("Creating embeddings...")
    linker.create_embeddings()
    # NOTE: returning without another pipe recreation


def main(model_pack_path: str, save_path: str):
    print("Loading", model_pack_path)
    cat = CAT.load_model_pack(model_pack_path)
    convert(cat)
    print("Saving to", save_path)
    saved = cat.save_model_pack(os.path.dirname(save_path),
                                pack_name=os.path.basename(save_path))
    print(f"Saved to\n{saved}")


if __name__ == "__main__":
    from sys import argv
    main(*argv[1:])
