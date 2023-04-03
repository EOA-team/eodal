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
from __future__ import annotations

import datetime
import dateutil.parser
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pickle
import xarray as xr

from collections.abc import MutableMapping
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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
        indexed_by_timestamps: Optional[bool] = True,
        *args,
        **kwargs,
    ):
        """
        Initializes a SceneCollection object with 0 to N scenes.

        :param scene_constructor:
            optional callable returning an `~eodal.core.raster.RasterCollection`
            instance.
        :param indexed_by_timestamps:
            if True, all scene indices are interpreted as timestamps (`datetime.datetime`).
            Set to False if scene indices should be treated as different data types
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
        self._is_sorted = True
        self._indexed_by_timestamps = indexed_by_timestamps

        self._identifiers = []
        if scene_constructor is not None:
            scene = scene_constructor.__call__(*args, **kwargs)
            self.__setitem__(scene)

    def __getitem__(self, key: str | slice) -> RasterCollection:
        def _get_scene_from_key(key: str | Any) -> RasterCollection:
            if self.indexed_by_timestamps:
                if str(key) in self.timestamps:
                    # most likely time stamps are passed as strings
                    # we infer the format using dateutil
                    key = dateutil.parser.parse(key)
                    return self.collection[key]
            else:
                if key in self.timestamps:
                    return self.collection[key]
            if key in self.identifiers:
                scene_idx = self.identifiers.index(key)
                return self.__getitem__(self.timestamps[scene_idx])

        # has a single key or slice been passed?
        if not isinstance(key, slice):
            try:
                return _get_scene_from_key(key=key)
            except IndexError:
                raise SceneNotFoundError(
                    f"Could not find a scene for key {key} in collection"
                )

        else:
            if not self.is_sorted:
                raise ValueError(
                    "Slices are not permitted on unsorted SceneCollections"
                )
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
                    if not self.indexed_by_timestamps:
                        raise ValueError(
                            "Cannot slice on timestamps when `indexed_by_timestamps` is False"
                        )
                    slice_start = list(self.collection.keys())[0].date()
                else:
                    if slice_end in self.identifiers:
                        slice_start = self.identifiers[0]
                    else:
                        slice_start = self.timestamps[0]
            # if end is None use the last scene
            end_increment = 0
            if slice_end is None:
                if isinstance(slice_start, datetime.date):
                    if not self.indexed_by_timestamps:
                        raise ValueError(
                            "Cannot slice on timestamps when `indexed_by_timestamps` is False"
                        )
                    slice_end = list(self.collection.keys())[-1].date()
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
            elif isinstance(slice_start, datetime.date) and isinstance(
                slice_end, datetime.date
            ):
                if not self.indexed_by_timestamps:
                    raise ValueError(
                        "Cannot slice on timestamps when `indexed_by_timestamps` is False"
                    )
                out_scoll = SceneCollection()
                for timestamp, scene in self:
                    if end_increment == 0:
                        if slice_start <= timestamp.date() < slice_end:
                            out_scoll.add_scene(scene.copy())
                    else:
                        if slice_start <= timestamp.date() <= slice_end:
                            out_scoll.add_scene(scene.copy())
                return out_scoll
            else:
                raise SceneNotFoundError(f"Could not find scenes in {key}")
            slice_step = key.step
            if slice_step is None:
                slice_step = 1
            # get an empty SceneCollection for returning the slide
            out_scoll = SceneCollection()
            for idx in range(idx_start, idx_end, slice_step):
                out_scoll.add_scene(_get_scene_from_key(key=scenes[idx]))
            return out_scoll

    def __getstate__(self):
        return self.__dict__.copy()

    def __setitem__(self, item: RasterCollection):
        if not isinstance(item, RasterCollection):
            raise TypeError("Only RasterCollection objects can be passed")
        if not item.is_scene:
            raise ValueError(
                "Only RasterCollection with timestamps in their scene_properties can be passed"
            )
        # scenes are index by their acquisition time
        key = item.scene_properties.acquisition_time
        if key in self.collection.keys():
            raise KeyError("Duplicate scene names are not permitted")
        if key is None:
            raise ValueError(
                "RasterCollection passed must have an acquisition time stamp"
            )
        # it's important to make a copy of the scene before adding it
        # to the collection
        value = deepcopy(item)
        self.collection[key] = value
        # last, use the scene uri as an alias if available
        if hasattr(item.scene_properties, "product_uri"):
            self._identifiers.append(item.scene_properties.product_uri)

    def __setstate__(self, d):
        self.collection = d

    def __delitem__(self, key: str | datetime.datetime):
        # get index of the scene to be deleted to also delete its identifier
        idx = self.timestamps.index(str(key))
        # casts strings back to datetime objects
        if isinstance(key, str):
            key = dateutil.parser.parse(key)
        del self.collection[key]
        _ = self.identifiers.pop(idx)

    def __iter__(self):
        for k, v in self.collection.items():
            yield k, v

    def __len__(self) -> int:
        return len(self.collection)

    def __repr__(self) -> str:
        if self.empty:
            return "Empty EOdal SceneCollection"
        else:
            if self.indexed_by_timestamps:
                timestamps = ", ".join(self.timestamps)
            else:
                timestamps = ", ".join([str(x) for x in self.timestamps])
            return (
                f"EOdal SceneCollection\n----------------------\n"
                + f"# Scenes:    {len(self)}\nTimestamps:    {timestamps}\n"
                + f'Scene Identifiers:    {", ".join(self.identifiers)}'
            )

    @property
    def indexed_by_timestamps(self) -> bool:
        return self._indexed_by_timestamps

    @staticmethod
    def _sort_keys(
        sort_direction: str,
        raster_collections: List[RasterCollection] | Tuple[RasterCollection],
    ) -> np.ndarray:
        """
        Returns sorted indices from a list/ tuple of RasterCollections.
        """
        # check sort_direction passed
        if sort_direction not in ["asc", "desc"]:
            raise ValueError("Sort direction must be one of: `asc`, `desc`")
        # get timestamps of the scenes and use np.argsort to bring them into the desired order
        timestamps = [x.scene_properties.acquisition_time for x in raster_collections]
        if sort_direction == "asc":
            sort_idx = np.argsort(timestamps)
        elif sort_direction == "desc":
            sort_idx = np.argsort(timestamps)[::-1]
        return sort_idx

    @property
    def empty(self) -> bool:
        """Scene Collection is empty"""
        return len(self) == 0

    @property
    def timestamps(self) -> List[str | Any]:
        """acquisition timestamps of scenes in collection"""
        if self.indexed_by_timestamps:
            return [str(x) for x in list(self.collection.keys())]
        else:
            return list(self.collection.keys())

    @property
    def identifiers(self) -> List[str]:
        """list of scene identifiers"""
        return self._identifiers

    @property
    def is_sorted(self) -> bool:
        """are the scenes sorted by their timstamps?"""
        return self._is_sorted

    @is_sorted.setter
    def is_sorted(self, value: bool) -> None:
        """are the scenes sorted by their timestamps?"""
        if not type(value) == bool:
            raise TypeError("Only boolean types are accepted")
        self._is_sorted = value

    @classmethod
    def from_pickle(cls, stream: bytes | Path):
        """
        Load SceneCollection from pickled binary stream.

        :param stream:
            pickled binary stream to load into a SceneCollection or
            file-path to pickled binary on disk.
        :returns:
            `SceneCollection` instance.
        """
        if isinstance(stream, Path):
            with open(stream, "rb") as f:
                reloaded = pickle.load(f)
        elif isinstance(stream, bytes):
            reloaded = pickle.loads(stream)
        else:
            raise TypeError(f"{type(stream)} is not a supported data type")
        # open empty scene collection and add scenes one by one
        scoll_out = cls()
        for _, scene in reloaded["collection"].items():
            scoll_out.add_scene(scene)
        return scoll_out

    @classmethod
    def from_raster_collections(
        cls,
        raster_collections: List[RasterCollection] | Tuple[RasterCollection],
        sort_scenes: Optional[bool] = True,
        sort_direction: Optional[str] = "asc",
        **kwargs,
    ):
        """
        Create a SceneCollection from a list/tuple of N RasterCollection objects.

        :param raster_collections:
            list or tuple of RasterCollections from which to create a new scene
            collection.
        :param sort_scenes:
            if True (default) scenes are order in chronological order by their
            acquisition time.
        :param sort_direction:
            direction of sorting. Must be either 'asc' (ascending) or 'desc'
            (descending). Ignored if `sort_scenes` is False.
        :param kwargs:
            key word arguments to pass to `SceneCollection` constructor call.
        :returns:
            SceneCollection instance
        """
        # check inputs
        if not isinstance(raster_collections, list) and not isinstance(
            raster_collections, tuple
        ):
            raise TypeError(f"Can only handle lists or tuples of RasterCollections")
        if not np.array(
            [isinstance(x, RasterCollection) for x in raster_collections]
        ).all():
            raise TypeError(f"All items passed must be RasterCollection instances")
        if not np.array([x.is_scene for x in raster_collections]).all():
            raise TypeError(f"All items passed must have an acquisition timestamp")
        # check if scenes shall be sorted
        if sort_scenes:
            sort_idx = cls._sort_keys(sort_direction, raster_collections)
            is_sorted = True
        else:
            sort_idx = np.array([x for x in range(len(raster_collections))])
            is_sorted = False
        # open a SceneCollection instance and add the scenes
        scoll = cls(**kwargs)
        scoll.is_sorted = is_sorted
        for idx in sort_idx:
            scoll.add_scene(scene_constructor=raster_collections[idx].copy())
        return scoll

    def add_scene(
        self,
        scene_constructor: Callable[..., RasterCollection] | RasterCollection,
        *args,
        **kwargs,
    ) -> None:
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
            raise ValueError(f"Cannot initialize new Scene instance: {e}")
        # try to add the scene to the SceneCollection
        try:
            self.__setitem__(scene)
        except Exception as e:
            raise KeyError(f"Cannot add scene: {e}")

    def apply(self, func: Callable, *args, **kwargs) -> Any:
        """
        Apply a custom function to a SceneCollection.

        :param func:
            custom callable taking the ``SceneCollection`` as first
            argument
        :param args:
            optional arguments to pass to `func`
        :param kwargs:
            optional keyword arguments to pass to `func`
        :returns:
            results of `func`
        """
        try:
            return func.__call__(self, *args, **kwargs)
        except Exception as e:
            raise ValueError from e

    def clip_scenes(self, inplace: Optional[bool] = False, **kwargs):
        """
        Clip scenes in a SceneCollection to a user-defined spatial bounds.

        :param inplace:
            if False (default) returns a copy of the ``SceneCollection`` instance
            with the changes applied. If True overwrites the values
            in the current instance.
        :param **kwargs:
            key-word arguments to pass to `RasterCollection.clip_bands` method.
        """
        # loop over Scenes and try to subset them spatially
        # initialize a new SceneCollection if inplace is False
        scoll_new = None
        if inplace:
            kwargs.update({"inplace": True})
        if not inplace:
            scoll_new = SceneCollection(
                indexed_by_timestamps=self.indexed_by_timestamps
            )
        # loop over band reproject the selected ones
        for timestamp, scene in self:
            if inplace:
                self[timestamp].clip_bands(**kwargs)
            else:
                scene = self[timestamp].copy()
                scoll_new.add_scene(scene_constructor=scene.clip_bands, **kwargs)

        if not inplace:
            return scoll_new

    def copy(self):
        """returns a true copy of the SceneCollection"""
        return deepcopy(self)

    def get_feature_timeseries(
        self,
        vector_features: Path | gpd.GeoDataFrame | str,
        reindex_dataframe: Optional[bool] = False,
        **kwargs,
    ) -> gpd.GeoDataFrame:
        """
        Get a time series for 1:N vector features from SceneCollection.

        :param vector_features:
            vector features for which to extract time series data. If `Point` geometries
            are provided calls `~RasterCollection.get_pixels()` on all scenes in the
            collection. If `Polygon` (or `MultiPolygons`) are provided, calls
            `~RasterCollection.band_summaries()` on all scenes in the collection.
        :param reindex_dataframe:
            boolean flag whether to reindex the resulting GeoDataFrame after extracting
            data from all scenes. Set to `True` to ensure that the returned GeoDataFrame
            has a unique index. `False` by default.
        :param kwargs:
            key word arguments to pass to `~RasterCollection.get_pixels()` or
            `~RasterCollection.band_summaries()` depending on the type of the input geometries.
        :returns:
            ``GeoDataFrame`` with extracted raster values per feature and time stamp
        """
        # check spatial datatypes
        if not isinstance(vector_features, str):
            if isinstance(vector_features, Path):
                gdf = gpd.read_file(vector_features)
            elif isinstance(vector_features, gpd.GeoDataFrame):
                gdf = vector_features.copy()
            else:
                raise ValueError(
                    'Can only handle pathlibo objects, GeoDataFrames or "self"'
                )
            if set(gdf.geometry.geom_type.unique()).issubset(
                set(["Point", "MulitPoint"])
            ):
                pixels = True
            elif set(gdf.geometry.geom_type.unique()).issubset(
                set(["Polygon", "MultiPolygon"])
            ):
                pixels = False
            else:
                raise ValueError(
                    "Can only handle (Multi)Point or (Multi)Polygon geometries"
                )
        else:
            if vector_features == "self":
                gdf = "self"
                pixels = False
            else:
                raise ValueError('When passing a string only "self" is permitted')

        # loop over scenes in collection and get the feature values
        gdf_list = []
        for timestamp, scene in self:
            if pixels:
                _gdf = scene.get_pixels(vector_features=gdf, **kwargs)
            else:
                _gdf = scene.band_summaries(by=gdf, **kwargs)
            _gdf["acquisition_time"] = timestamp
            gdf_list.append(_gdf)
        # reindex the resulting GeoDataFrame if required
        if reindex_dataframe:
            gdf = pd.concat(gdf_list)
            # reindexing is done by counting the features starting from zero
            gdf.index = [x for x in range(gdf.shape[0])]
            return gdf
        else:
            return pd.concat(gdf_list)

    def plot(
        self,
        band_selection: str | List[str],
        max_scenes_in_row: Optional[int] = 6,
        eodal_plot_kwargs: Optional[Dict] = {},
        **kwargs,
    ) -> plt.Figure:
        """
        Plots scenes in a `SceneCollection`

        :param band_selection:
            selection of band(s) to use for plotting. Must be either a single
            band or a set of three bands
        :param max_scenes_in_row:
            number of scenes in a row. Set to 6 by default.
        :param eodal_plot_kwargs:
            optional keyword arguments to pass on to `eodal.core.band.Band.plot()`
        :param kwargs:
            optional keyword arguments to pass to `matplotlib.subplots()`.
        :returns:
            `Figure` object
        """
        # check number of passed bands
        if isinstance(band_selection, str):
            band_selection = [band_selection]
        if not len(band_selection) == 1 and not len(band_selection) == 3:
            raise ValueError("You must pass a single band name or three band names")

        plot_multiple_bands = True
        if len(band_selection) == 1:
            plot_multiple_bands = False

        # check number of mapper in feature_scenes and determine figure size
        n_scenes = len(self)
        nrows = 1
        ncols = 1
        if self.empty:
            raise ValueError("No scenes available for plotting")
        elif n_scenes == 1:
            f, ax = plt.subplots(**kwargs)
            # cast to array to allow indexing
            ax = np.array([ax]).reshape(1, 1)
        else:
            if n_scenes <= max_scenes_in_row:
                ncols = n_scenes
                f, ax = plt.subplots(ncols=ncols, nrows=nrows, **kwargs)
                # reshape to match the shape of ax array with >1 rows
                ax = ax.reshape(1, ax.size)
            else:
                nrows = int(np.ceil(n_scenes / max_scenes_in_row))
                ncols = max_scenes_in_row
                f, ax = plt.subplots(ncols=ncols, nrows=nrows, **kwargs)
        # get scene labels
        scene_labels = list(self.collection.keys())

        row_idx, col_idx = 0, 0
        idx = 0
        for idx, _scene in enumerate(self):
            scene = _scene[1]
            if plot_multiple_bands:
                scene.plot_multiple_bands(
                    band_selection=band_selection,
                    ax=ax[row_idx, col_idx],
                    **eodal_plot_kwargs,
                )
            else:
                scene[band_selection[0]].plot(
                    ax=ax[row_idx, col_idx], **eodal_plot_kwargs
                )
            ax[row_idx, col_idx].set_title(scene_labels[idx])
            idx += 1

            # switch off axes labels if sharex == True and sharey=True
            if (
                kwargs.get("sharex", False)
                and kwargs.get("sharey", False)
                and n_scenes > 1
            ):
                if nrows > 1:
                    if row_idx < (nrows - 1):
                        ax[row_idx, col_idx].set_xlabel("")
                if nrows > 1:
                    if col_idx > 0:
                        ax[row_idx, col_idx].set_ylabel("")

            # increase column (and row) counter accordingly
            col_idx += 1
            # begin a new row when all columns are filled
            if col_idx == max_scenes_in_row:
                col_idx = 0
                row_idx += 1

        # make sure sub-plot labels do not overlap
        f.tight_layout()
        return f

    def sort(self, sort_direction: Optional[str] = "asc"):
        """
        Returns a sorted copy of the SceneCollection.

        :param sort_direction:
            direction of sorting. Must be either 'asc' (ascending) or 'desc'
            (descending). Ignored if `sort_scenes` is False.
        :returns:
            sorted SceneCollection.
        """
        # empty SceneCollections cannot be sorted
        if self.empty:
            return self.copy()
        # get a list of all scenes in the collection and sort them
        scenes = [v for _, v in self]
        sort_idx = self._sort_keys(sort_direction, raster_collections=scenes)
        scoll = SceneCollection()
        for idx in sort_idx:
            scoll.add_scene(scenes[idx].copy())
        return scoll

    def to_pickle(self) -> bytes:
        """
        Dumps a scene collection as pickled object

        :returns:
            pickled binary object
        """
        return pickle.dumps(self.__dict__.copy())

    def to_xarray(self, **kwargs) -> xr.DataArray:
        """
        Converts all scenes in a SceneCollection to a single `xarray.DataArray`.

        :param kwargs:
            key word arguments to pass to `~RasterCollection.to_xarray`
        :returns:
            SceneCollection as `xarray.DataArray`
        """
        # loop over scenes in Collection and convert them to xarray.DataArray
        xarray_list = []
        for timestamp, scene in self:
            _xr = scene.to_xarray(**kwargs)
            # _xr = _xr.to_dataset()
            _xr = _xr.expand_dims(time=[timestamp])
            xarray_list.append(_xr)
        # concatenate into a single xarray along the time dimension
        return xr.concat(xarray_list, dim="time")
