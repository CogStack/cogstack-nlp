from medcat.cat import CAT

from medcat_den import wrappers

from .test_file_system_den import def_model_pack


def wrap(cat: CAT) -> wrappers.CATWrapper:
    # creates a new pipe!
    return wrappers.CATWrapper(cat.cdb, cat.vocab, cat.config)


def test_wrapper_saves_as_CAT(tmpdir, def_model_pack):
    cat = wrap(def_model_pack)
    mpp = cat.save_model_pack(tmpdir, force_save_local=True)
    loaded = CAT.load_model_pack(mpp)
    assert isinstance(loaded, CAT)
