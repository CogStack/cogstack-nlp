from typing import Union, overload
import numpy as np
from numpy.typing import NDArray


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


@overload
def sigmoid(x: float) -> float:
    pass


@overload
def sigmoid(x: NDArray[np.float64]) -> NDArray[np.float64]:
    pass


def sigmoid(x: Union[np.ndarray, float]) -> Union[np.ndarray, float]:
    return 1 / (1 + np.exp(-x))
