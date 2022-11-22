"""
A scene is a collection of raster bands with an acquisition date, an unique identifier
and a (remote sensing) platform that acquired the raster data.

Copyright (C) 2022 Lukas Valentin Graf

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from collections.abc import MutableMapping
from typing import Callable, List, Optional

import eodal.core.raster as raster

class SceneCollection(MutableMapping):
    """
    Collection of 0:N scenes where each scene is a RasterCollection with
    **non-empty** `SceneProperties` as each scene is indexed by its
    acquistion time.
    """
    def __init__(
        self,
        scene_constructor: Optional[Callable[..., raster.RasterCollection]] = None,
        *args,
        **kwargs
    ):
        """
        Initializes a SceneCollection object with 0 to N scenes.

         :param scene_constructor:
            optional callable returning an `~eodal.core.raster.RasterCollection`
            instance.
        :param args:
            arguments to pass to `scene_constructor` or one of RasterCollection's
            class methods (e.g., `RasterCollection.from_multi_band_raster`)
        :param kwargs:
            key-word arguments to pass to `scene_constructor` or one of RasterCollection's
            class methods (e.g., `RasterCollection.from_multi_band_raster`)
        """
        # mapper are stored in a dictionary like collection
        self._frozen = False
        self.collection = dict()
        self._frozen = True

        if scene_constructor is not None:
            scene = scene_constructor.__call__(*args, **kwargs)
            if not isinstance(scene, raster.RasterCollection):
                raise TypeError('Only RasterCollection objects can be passed')
            self.__setitem__(scene)

    def __getitem__(self, key: str) -> raster.RasterCollection:
        return self.collection[key]

    def __setitem__(self, item: raster.RasterCollection):
        if not isinstance(item, raster.RasterCollection):
            raise TypeError("Only RasterCollection objects can be passed")
        key = item.scene_properties.acquisition_time
        if key in self.collection.keys():
            raise KeyError("Duplicate scene names are not permitted")
        if key is None:
            raise ValueError("RasterCollection passed must have an acquistion time stamp")
        value = item.copy()
        self.collection[key] = value

    def __delitem__(self, key: str):
        del self.collection[key]

    def __iter__(self):
        for k, v in self.collection.items():
            yield k, v

    def __len__(self) -> int:
        return len(self.collection)

    def __repr__(self) -> str:
        return ''

    @property
    def scene_names(self) -> List[str]:
        """scene names in collection"""
        return list(self.collection.keys())

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
