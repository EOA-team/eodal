"""
A SceneCollection is a collection of scenes. A Scene is a RasterCollections with an
acquisition date, an unique identifier and a (remote sensing) platform that acquired
the raster data.

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

import datetime
import dateutil.parser

from collections.abc import MutableMapping
from copy import deepcopy
from typing import Callable, List, Optional

from eodal.core.raster import RasterCollection
from eodal.utils.exceptions import SceneNotFoundError

class SceneCollection(MutableMapping):
    """
    Collection of 0:N scenes where each scene is a RasterCollection with
    **non-empty** `SceneProperties` as each scene is indexed by its
    acquistion time.
    """
    def __init__(
        self,
        scene_constructor: Optional[Callable[..., RasterCollection]] = None,
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

        self._identifiers = []
        if scene_constructor is not None:
            scene = scene_constructor.__call__(*args, **kwargs)
            self.__setitem__(scene)

    def __getitem__(self, key: str | slice) -> RasterCollection:

        def _get_scene_from_key(key: str) -> RasterCollection:
            if key in self.timestamps:
                # most likely time stamps are passed as strings
                if isinstance(key, str):
                    # we infer the format using dateutil
                    key = dateutil.parser.parse(key)
                return self.__getitem__(key)
            elif key in self.identifiers:
                scene_idx = self.identifiers.index(key)
                return self.__getitem__(self.timestamps[scene_idx])

        # has a single key or slice been passed?
        if isinstance(key, str):
            try:
                return _get_scene_from_key(key=key)
            except IndexError:
                raise SceneNotFoundError(
                    f'Could not find a scene for key {key} in collection'
                )

        elif isinstance(key, slice):
            # find the index of the start and the end of the slice
            slice_start = key.start
            slice_end = key.stop
            # return an empty SceneCollection if start and stop is the same
            # (numpy array behavior)
            if slice_start is None and slice_end is None:
                return SceneCollection()
            # if start is None use the first scene
            if slice_start is None:
                if isinstance(slice_end, datetime.date):
                    slice_start = self.timestamps[0].date()
                else:
                    if slice_end in self.identifiers:
                        slice_start = self.identifiers[0]
                    else:
                        slice_start = self.timestamps[0]
            # if end is None use the last scene
            end_increment = 0
            if slice_end is None:
                if isinstance(slice_start, datetime.date):
                    slice_end = self.timestamps[-1].date()
                else:
                    if slice_start in self.identifiers:
                        slice_end = self.identifiers[-1]
                    else:
                        slice_end = self.timestamps[-1]
                # to ensure that the :: operator works, we need to make
                # sure the last band is also included in the slice
                end_increment = 1
            
            if set([slice_start, slice_end]).issubset(set(self.timestamps)):
                idx_start = self.timestamps.index(slice_start)
                idx_end = self.timestamps.index(slice_end) + end_increment
                scenes = self.timestamps
            elif set([slice_start, slice_end]).issubset(set(self.identifiers)):
                idx_start = self.identifiers.index(slice_start)
                idx_end = self.identifiers.index(slice_end) + end_increment
                scenes = self.identifiers
            # allow selection by date range
            elif isinstance(slice_start, datetime.date) and isinstance(slice_end, datetime.date):
                out_scoll = SceneCollection()
                for timestamp, scene in self:
                    if slice_start <= timestamp < slice_end:
                        out_scoll.add_scene(scene.copy())
                return out_scoll
            else:
                raise SceneNotFoundError(f'Could not find scenes in {key}')
            slice_step = key.step
            if slice_step is None:
                slice_step = 1
            # get an empty SceneCollection for returning the slide
            out_scoll = SceneCollection()
            for idx in range(idx_start, idx_end, slice_step):
                out_scoll.add_scene(_get_scene_from_key(key=scenes[idx]))
            return out_scoll

    def __setitem__(self, item: RasterCollection):
        if not isinstance(item, RasterCollection):
            raise TypeError("Only RasterCollection objects can be passed")
        if not item.is_scene:
            raise ValueError(
                'Only RasterCollection with timestamps in their scene_properties can be passed'
            )
        # use the scene uri as an alias if available
        if hasattr(item.scene_properties, 'product_uri'):
            self._identifiers.append(item.scene_properties.product_uri)
        # scenes are index by their acquisition time
        key = item.scene_properties.acquisition_time
        if key in self.collection.keys():
            raise KeyError("Duplicate scene names are not permitted")
        if key is None:
            raise ValueError("RasterCollection passed must have an acquisition time stamp")
        # it's important to make a copy of the scene before adding it
        # to the collection
        value = deepcopy(item)
        self.collection[key] = value

    def __delitem__(self, key: str):
        del self.collection[key]

    def __iter__(self):
        for k, v in self.collection.items():
            yield k, v

    def __len__(self) -> int:
        return len(self.collection)

    def __repr__(self) -> str:
        if self.empty:
            return 'Empty EOdal SceneCollection'
        else:
            return f'EOdal SceneCollection\n----------------------\n' + \
                f'# Scenes:    {len(self)}\nTimestamps:    {", ".join(self.timestamps)}\n' +  \
                f'Scene Identifiers:    {", ".join(self.identifiers)}'

    @property
    def empty(self) -> bool:
        """Scene Collection is empty"""
        return len(self) == 0

    @property
    def timestamps(self) -> List[str]:
        """acquisition timestamps of scenes in collection"""
        return [str(x) for x in list(self.collection.keys())]

    @property
    def identifiers(self) -> List[str]:
        """list of scene identifiers"""
        return self._identifiers

    def add_scene(
        self, scene_constructor: Callable[...,RasterCollection] | RasterCollection, *args, **kwargs
    ):
        """
        Adds a Scene to the collection of scenes.

        Raises an error if a scene with the same timestamp already exists (unique
        timestamp constraint)

        :param scene_constructor:
            callable returning a `~eodal.core.raster.RasterCollection` instance or
            existing `RasterCollection` instance
        :param args:
            positional arguments to pass to `scene_constructor`
        :param kwargs:
            keyword arguments to pass to `scene_constructor`
        """
        # if a RasterCollection is passed no constructor call is required
        try:
            if isinstance(scene_constructor, RasterCollection):
                scene = scene_constructor
            else:
                scene = scene_constructor.__call__(*args, **kwargs)
        except Exception as e:
            raise ValueError(f'Cannot initialize new Scene instance: {e}')
        # try to add the scene to the SceneCollection
        try:
            self.__setitem__(scene)
        except Exception as e:
            raise KeyError(f'Cannot add scene: {e}')


    def apply(self, func: Callable):
        pass

    def dump(self):
        pass

    def get_pixels(self):
        pass

    def load(self):
        pass

    def plot(self):
        pass

    def to_xarray(self):
        pass
