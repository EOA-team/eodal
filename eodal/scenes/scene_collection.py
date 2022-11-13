'''
Created on Nov 13, 2022

@author: graflu
'''

import pandas as pd

from eodal.core.raster import RasterCollection

class Scene:

    def __init__(self, metadata: pd.Series, data: RasterCollection):
        """
        """
        self._metadata = metadata
        self._data = data

    @property
    def metadata(self) -> pd.Series:
        return self._metadata

    @property
    def data(self) -> RasterCollection:
        return self._data

class SceneCollection:
    def __init__(self):
        pass

    def __repr__(self) -> str:
        pass

    def apply(self):
        pass

    def dump(self):
        pass

    def filter(self):
        pass

    def load(self):
        pass

    def plot(self):
        pass

    def to_xarray(self):
        pass
