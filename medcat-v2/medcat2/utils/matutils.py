import numpy as np


# NOTE: this would be faster with `gensim`
#       since it uses BLAS, but can't get it to
#       work well with numpy2/scipy combo
def unitvec(vec: np.ndarray) -> np.ndarray:
    """Get the unitvector.

    Args:
        vec (np.ndarray): The non-unit vector.

    Returns:
        np.ndarray: The new unit vector.
    """
    return vec / np.linalg.norm(vec)
