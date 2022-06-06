"""
Module provides a simple cubic_rectification function.
"""

import numpy as np


def cubic_rectification(x, verbose=False):
    """
    Rectified cube of an array.

    Parameters
    ----------
    x : numpy.ndarray
        Input array.
    verbose : bool, optional
        Whether to print out details. Default is ``False``.

    Returns
    -------
    numpy.ndarray
        Elementwise, the cube of `x` where it is positive and ``0`` otherwise.

    Note
    ----
    This is a sample function, using a numpy docstring format.

    Note
    ----
    The use of intersphinx will cause :class:`numpy.ndarray` to link to
    the numpy documentation page.
    """
    if verbose:
        print("Cubing and then rectifying {}".format(x))
    return np.maximum(0, x**3)
