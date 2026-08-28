import dill

from medcat.vocab import Vocab


def get_vocab_from_old(old_path: str) -> Vocab:
    """Convert a v1 vocab file to a v2 Vocab.

    Args:
        old_path (str): The v1 vocab file path.

    Returns:
        Vocab: The v2 Vocab.
    """
    with open(old_path, 'rb') as f:
        data = dill.load(f)
    v = Vocab()
    for word, word_data in data['vocab'].items():
        v.add_word(word, cnt=word_data['cnt'], vec=word_data['vec'],
                   replace=True)
    v.init_cumsums()
    return v
