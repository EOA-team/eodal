from __future__ import annotations

import numpy as np


# ranking of Python data types according to numpy
DATATYPES = [
    np.dtype('int'), np.dtype('int8'), np.dtype('int16'),
    np.dtype('int32'),np.dtype('int64'), np.dtype('uint'),
    np.dtype('uint8'), np.dtype('uint16'), np.dtype('uint32'),
    np.dtype('uint64'), np.dtype('float16'), np.dtype('float32'),
    np.dtype('float64'), np.dtype('complex64'),
    np.dtype('complex128')
]
DTYPE_RANKS = {x: x.num for x in DATATYPES}


def get_rank(dtype: np.dtype | str) -> int:
    """
    Get the rank of a data type

    :param dtype: data type for which to get the rank.
    :return: rank of `dtype` as defined by `numpy`.
    """
    if dtype in DTYPE_RANKS:
        return DTYPE_RANKS[dtype]
    else:
        raise ValueError(f"Unknown data type: {dtype}")


def get_highest_dtype(dtype_list: list[np.dtype | str]) -> np.dtype | str:
    """
    Get the highest data type of a list of data types based
    on the data types ranks defined by `numpy`

    :param dtype_list: list of data types
    :return: higest data type in its `numpy.dtype` or string representation
    """
    return max(dtype_list, key=get_rank)
