'''
Created on Nov 13, 2022

@author: graflu
'''

import pandas as pd

from typing import Callable

from eodal.core.raster import RasterCollection
from eodal.core.scene import SceneProperties

class Scene:

    def __init__(self, data: RasterCollection):
        """
        Class constructor

        :param data:
            scene data as `RasterCollection`
        """
        self._data = data
        # set metadata using the SceneProperties from RasterCollection
        self._metadata = data.scene_properties

    @property
    def metadata(self) -> SceneProperties:
        """scene metadata"""
        return self._metadata

    @property
    def data(self) -> RasterCollection:
        """scene data"""
        return self._data

class SceneCollection:
    def __init__(self):
        pass

    def __repr__(self) -> str:
        pass

    def apply(self, func: Callable):
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
