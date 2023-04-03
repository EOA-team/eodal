"""
The EOdal `Mapper` class allows to extract and handle EO data in space and time
and bring the data into Analysis-Ready-Format (ARD).

.. versionadded:: 0.2.0

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

import cv2
import eodal
import geopandas as gpd
import getpass
import numpy as np
import pandas as pd
import warnings
import uuid
import yaml

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from sqlalchemy.exc import DatabaseError
from shapely.geometry import box
from typing import Any, Callable, Dict, List, Optional

from eodal.config import get_settings
from eodal.core.algorithms import merge_datasets
from eodal.core.raster import RasterCollection
from eodal.core.scene import SceneCollection
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.metadata.database.querying import find_raw_data_by_bbox
from eodal.metadata.utils import reconstruct_path
from eodal.utils.exceptions import STACError

settings = get_settings()
logger = settings.logger


class MapperConfigs:
    """
    global configurations of the Mapper class defining metadata search
    criteria (space and time), data collections to search and behavior
    for bringing data into analysis-ready-format (ARD)

    :attrib collection:
        name of the collection (<platform>-<sensor>-<processing level>) to use.
        E.g., "Sentinel2-MSI-L2A
    :attrib feature:
        geographic feature(s) for which to extract data from collection
    :atrrib time_start:
        time stamp from which onwards to extract data from collection
    :atrrib time_end:
        time stamp till which to extract data from collection
    :attrib metadata_filters:
        list of custom metadata filters to shrink collection to.
        Examples include cloud cover filters in the case of optical data
        or filter by incidence angle in the case of SAR observations.
    """

    def __init__(
        self,
        collection: str,
        feature: Feature,
        time_start: datetime,
        time_end: datetime,
        metadata_filters: Optional[List[Filter]] = None,
    ):
        """
        default class constructor

        :param collection:
            name of the collection (<platform>-<sensor>) to use.
            E.g., "sentinel2-msi". <sensor> is optional and can be omitted
            if a platform does not carry more than a single sensor. I.e.,
            one could also pass "sentinel2" instead.
        :param feature:
            geographic feature(s) for which to extract data from collection
        :param time_start:
            time stamp from which onwards to extract data from collection
        :param time_end:
            time stamp till which to extract data from collection
        :param  metadata_filters:
            list of custom metadata filters to shrink collection to.
            Examples include cloud cover filters in the case of optical data
            or filter by incidence angle in the case of SAR observations.
        """
        # check inputs
        if not isinstance(collection, str):
            raise TypeError("Collection must be a string")

        if len(collection) < 3:
            raise ValueError("Collections must have at least 3 characters")
        if collection.count("-") > 2:
            raise ValueError(
                f"Collections must obey the format <platform>-<sensor> where <sesor> is optional"
            )
        if not isinstance(feature, Feature):
            raise TypeError("Expected a Feature object")
        if not isinstance(time_start, datetime) and not isinstance(time_end, datetime):
            raise TypeError("Expected datetime objects")
        if metadata_filters is not None:
            if not np.array([isinstance(x, Filter) for x in metadata_filters]).all():
                raise TypeError("All filters must be instances of the Filter class")

        self._collection = collection
        self._feature = feature
        self._time_start = time_start
        self._time_end = time_end
        self._metadata_filters = metadata_filters

    def __repr__(self) -> str:
        return (
            f"EOdal MapperConfig\n------------------\nCollection: {self.collection}"
            + f"\nTime Range: {self.time_start} - {self.time_end}\nFeature:\n"
            + f"{self.feature.__repr__()}\nMetadata Filters: {str(self.metadata_filters)}"
        )

    @property
    def collection(self) -> str:
        return self._collection

    @property
    def platform(self) -> str:
        return self.collection.split("-")[0]

    @property
    def sensor(self) -> str:
        try:
            return self._collection.split("-")[1]
        except IndexError:
            return ""

    @property
    def feature(self) -> Feature:
        return self._feature

    @property
    def time_start(self) -> datetime:
        return self._time_start

    @property
    def time_end(self) -> datetime:
        return self._time_end

    @property
    def metadata_filters(self) -> List[Filter] | None:
        return self._metadata_filters

    @classmethod
    def from_yaml(cls, fpath: str | Path) -> cls:
        """
        Load mapping configurations from YAML file

        :param fpath:
            file-path to yaml with Mapper configurations
        :returns:
            new `MapperConfigs` instance
        """
        with open(fpath, "r") as f:
            try:
                yaml_content = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                print(exc)
        # reconstruct the Featue object first
        if "feature" not in yaml_content.keys():
            raise ValueError('"feature" attribute is required"')
        feature_yaml = yaml_content["feature"]
        # reconstruct the filter objects
        filter_list = []
        if "metadata_filters" in yaml_content.keys():
            filters_yaml = yaml_content["metadata_filters"]
            for filter_yaml in filters_yaml:
                filter_list.append(Filter(*filter_yaml.split()))
        try:
            feature = Feature.from_dict(feature_yaml)
            return cls(
                collection=yaml_content["collection"],
                feature=feature,
                time_start=yaml_content["time_start"],
                time_end=yaml_content["time_end"],
                metadata_filters=filter_list,
            )
        except KeyError as e:
            raise ValueError(f"Missing keys in yaml file: {e}")

    def to_yaml(self, fpath: str | Path) -> None:
        """
        save MapperConfig and some meta-information to YAML file (*.yml)

        :param fpath:
            file-path where saving the Feature instance to
        """
        mapper_configs_dict = {}
        mapper_configs_dict["collection"] = self.collection
        mapper_configs_dict["feature"] = self.feature.to_dict()
        mapper_configs_dict["time_start"] = self.time_start
        mapper_configs_dict["time_end"] = self.time_end
        mapper_configs_dict["metadata_filters"] = [
            x.__repr__() for x in self.metadata_filters
        ]
        # add some meta-information about creation time and current user
        mapper_configs_dict["created_at"] = datetime.now()
        mapper_configs_dict["created_by"] = getpass.getuser()
        mapper_configs_dict["eodal_version"] = eodal.__version__

        with open(fpath, "w+") as f:
            yaml.dump(mapper_configs_dict, f, allow_unicode=True)


class Mapper:
    """
    Generic class for mapping Earth Observation Data across space and time
    and bring them into Analysis-Readay-Format (ARD).

    The mapper class takes over searching for EO scenes, merging them and
    filling eventually occurring black-fill (no-data regions).

    :attrib mapper_configs:
        `MapperConfig` instance defining search criteria
    :attrib data:
        loaded scene data as EOdal `SceneCollection`
    :attrib metadata:
        corresponding scene metadata as `GeoDataFrame`.
    """

    def __init__(
        self, mapper_configs: MapperConfigs, time_column: Optional[str] = "sensing_time"
    ):
        """
        Class constructor

        :param mapper_configs:
            `MapperConfig` instance defining search criteria
        :param time_column:
            name of the metadata column denoting the time stamps of the scenes.
            `sensing_time` by default.
        """
        if not isinstance(mapper_configs, MapperConfigs):
            raise TypeError(f"Expected a MapperConfigs instance")
        self._mapper_configs = mapper_configs
        self._time_column = time_column
        self._metadata = None
        self._sensor = self.mapper_configs.collection.split("-")[0]
        self._data = None
        self._geoms_are_points = False

    def __repr__(self) -> str:
        return f"EOdal Mapper\n============\n{self.mapper_configs.__repr__()}"

    @property
    def data(self) -> None | SceneCollection | gpd.GeoDataFrame:
        """
        SceneCollection with scenes found or GeoDataFrame in case
        single pixel values are extracted
        """
        return self._data

    @data.setter
    def data(self, scoll: Optional[SceneCollection] = None):
        if scoll is not None:
            if not isinstance(scoll, SceneCollection) and not isinstance(
                scoll, gpd.GeoDataFrame
            ):
                raise TypeError("Expected a EOdal SceneCollection or GeoDataFrame")
        self._data = scoll

    @property
    def mapper_configs(self) -> MapperConfigs:
        """mapper configurations"""
        return self._mapper_configs

    @property
    def metadata(self) -> None | gpd.GeoDataFrame:
        """scene metadata found"""
        return self._metadata

    @metadata.setter
    def metadata(self, values: Optional[gpd.GeoDataFrame] = None):
        """set scene metadata"""
        if values is not None:
            if not isinstance(values, gpd.GeoDataFrame):
                raise TypeError("Expected a GeoDataFrame")
        self._metadata = deepcopy(values)

    @property
    def sensor(self) -> str | None:
        return self._sensor

    @property
    def time_column(self) -> str:
        return self._time_column

    def query_scenes(self) -> None:
        """
        Query available scenes for the current `MapperConfigs` and loads
        into the `observations` attribute.

        Depending on the settings of EOdal, this method either makes a
        query to a STAC resource or to a PostgreSQL/PostGIS database.

        NOTE:
            This method only queries a metadata catalog without reading data.
        """
        # check for point geometries
        self._geoms_are_points = self.mapper_configs.feature.geometry.geom_type in [
            "Point",
            "MultiPoint",
        ]

        # determine bounding box of the feature using
        # its representation in geographic coordinates (WGS84, EPSG: 4326)
        feature_wgs84 = self.mapper_configs.feature.to_epsg(4326)
        bbox = box(*feature_wgs84.geometry.bounds)

        # determine platform
        platform = self.mapper_configs.platform

        # put kwargs together
        kwargs = {
            "platform": platform,
            "time_start": self.mapper_configs.time_start,
            "time_end": self.mapper_configs.time_end,
            "bounding_box": bbox,
            "metadata_filters": self.mapper_configs.metadata_filters,
        }

        # query the metadata catalog (STAC or database depending on settings)
        if settings.USE_STAC:
            try:
                exec(f"from eodal.metadata.stac import {platform}")
                scenes_df = eval(f"{platform}(**kwargs)")
            except Exception as e:
                raise STACError(f"Querying STAC catalog failed: {e}")
        else:
            try:
                scenes_df = find_raw_data_by_bbox(**kwargs)
            except Exception as e:
                raise DatabaseError(f"Querying metadata DB failed: {e}")

        # populate the metadata attribute
        self.metadata = scenes_df

    def _process_scene(
        self,
        item: pd.Series,
        scene_constructor: Callable[..., RasterCollection],
        scene_constructor_kwargs: Dict[str, Any],
        scene_modifier: Callable[..., RasterCollection],
        scene_modifier_kwargs: Dict[str, Any],
        reprojection_method: int,
    ) -> RasterCollection:
        """
        Pre-process a scene so it can be added to a SceneCollection.
        This includes applying user-defined reading and modification functions.
        In addition, the `Scene` is projected into the target spatial reference
        system by using the reference system the majority of the scenes in a
        collection has in common.

        IMPORTANT:
            The reprojection step into the target spatial reference system (if
            scene is not projected in it already) is **always** done!

        :param item:
            metadata item of the scene including its file-path or URL
        :param scene_constructor:
            Callable used to read the scenes found into `RasterCollection` fulfilling
            the `is_scene` criterion (i.e., a time stamp is available).
        :param scene_constructor_kwargs:
            keyword-arguments to pass to `scene_constructor`. `fpath_raster`
            and `vector_features` are filled in by the `Mapper` instance automatically,
        :param scene_modifier:
            optional Callable modifying a `RasterCollection` or returning a new
            `RasterCollection`.
        :param scene_modifier_kwargs:
            keyword arguments for `scene_modifier`
        :returns:
            `Scene` with all pre-processing steps applied.
        """
        scene_constructor_kwargs.update(
            {"vector_features": self.mapper_configs.feature.to_geoseries()}
        )
        try:
            # call scene constructor. The file-path (or URL) goes first
            scene = scene_constructor.__call__(
                item.real_path, **scene_constructor_kwargs
            )
            scene.scene_properties.sensing_time = item[self.time_column]
        except Exception as e:
            raise ValueError(f"Could not load scene:  {e}")

        # apply scene modifier callable if available
        if scene_modifier is not None:
            scene = scene_modifier.__call__(scene, **scene_modifier_kwargs)

        # reproject scene if necessary
        scene.reproject(
            target_crs=item.target_epsg,
            interpolation_method=reprojection_method,
            inplace=True,
        )

        return scene

    def _load_scenes_collection(
        self,
        reprojection_method: Optional[int] = cv2.INTER_NEAREST_EXACT,
        scene_constructor: Optional[
            Callable[..., RasterCollection]
        ] = RasterCollection.from_multi_band_raster,
        scene_constructor_kwargs: Optional[Dict[str, Any]] = {},
        scene_modifier: Optional[Callable[..., RasterCollection]] = None,
        scene_modifier_kwargs: Optional[Dict[str, Any]] = {},
    ) -> None:
        """
        Auxiliary method to handle EOdal scenes and store them into a SceneCollection.

        This method is called when the geometries used for calling the `Mapper`
        instance are of type `Polygon` or `MultiPolygon`.

        Mosaicing operations are handled on the fly so calling programs will
        always receive analysis-ready data.

        :param scene_constructor:
            Callable used to read the scenes found into `RasterCollection` fulfilling
            the `is_scene` criterion (i.e., a time stamp is available). The callable is
            applied to all scenes found in the metadata query call.
            By default the standard class-method call `~RasterCollection.from_multi_band_raster`
            is used. It can be replaced, however, with a custom-written callable that
            can be of any design except that it **MUST** accept a keyword argument
            `fpath_raster` used for reading the Scene data and `vector_features` for
            cropping the data to the spatial extent of the Mapper instance.
        :param scene_constructor_kwargs:
            optional keyword-arguments to pass to `scene_constructor`. `fpath_raster`
            and `vector_features` are filled in by the `Mapper` instance automatically,
            i.e., any custom values passed will be overwritten.
        :param scene_modifier:
            optional Callable modifying a `RasterCollection` or returning a new
            `RasterCollection`. The Callable is applied to all scenes in the
            `SceneCollection` when loaded by the `Mapper`. Can be used, e.g.,
            to calculate spectral indices on the fly or for applying masks.
        :param scene_modifier_kwargs:
            optional keyword arguments for `scene_modifier` (if any).
        """
        # open a SceneCollection for storing the data
        scoll = SceneCollection()
        logger.info(f"Starting extraction of {self.sensor} scenes")
        # filter out datasets where mosaicing is necessary (time stamp is the same)
        self.metadata["_duplicated"] = self.metadata[self.time_column].duplicated(
            keep=False
        )
        # datasets where the 'duplicated' entry is False are truely unqiue
        _metadata_unique = self.metadata[~self.metadata._duplicated].copy()
        _metadata_nonunique = self.metadata[self.metadata._duplicated].copy()

        # mosaic the non-unique datasets first
        if not _metadata_nonunique.empty:
            _metadata_nonunique.sort_values(by=self.time_column, inplace=True)
            unique_time_stamps = _metadata_nonunique[self.time_column].unique()
            # loop over unique time stamps. In the end there should be a single
            # scene per time stamp
            update_scene_properties_list = []
            for unique_time_stamp in unique_time_stamps:
                scenes = _metadata_nonunique[
                    _metadata_nonunique[self.time_column].dt.strftime("%Y-%m-%d %H:%M")
                    == pd.to_datetime(unique_time_stamp).strftime("%Y-%m-%d %H:%M")[
                        0:16
                    ]
                ]
                # read the datasets one by one, save them into a temporary directory
                # and merge them using rasterio
                dataset_list = []
                scene_properties_list = []
                for _, item in scenes.iterrows():
                    _scene = self._process_scene(
                        item=item,
                        scene_constructor=scene_constructor,
                        scene_constructor_kwargs=scene_constructor_kwargs,
                        reprojection_method=reprojection_method,
                        scene_modifier=scene_modifier,
                        scene_modifier_kwargs=scene_modifier_kwargs,
                    )
                    fname_scene = settings.TEMP_WORKING_DIR.joinpath(
                        f"{uuid.uuid4()}.tif"
                    )
                    _scene.to_rasterio(fname_scene)
                    dataset_list.append(fname_scene)
                    scene_properties_list.append(_scene.scene_properties)
                # merge datasets using rasterio and read results back into a scene
                band_options = {
                    "band_names": _scene.band_names,
                    "band_aliases": _scene.band_aliases,
                }
                scene = merge_datasets(
                    datasets=dataset_list,
                    target_crs=self.metadata.target_epsg.unique()[0],
                    vector_features=self.mapper_configs.feature.to_geoseries(),
                    sensor=self.sensor,
                    band_options=band_options,
                )
                # handle scene properties. They need to be merged as well
                merged_scene_properties = scene_properties_list[0]
                for other_scene_properties in scene_properties_list[1::]:
                    scene_props_keys = list(merged_scene_properties.__dict__.keys())
                    for scene_prop in scene_props_keys:
                        first_val = eval(f"merged_scene_properties.{scene_prop}")
                        this_val = eval(f"other_scene_properties.{scene_prop}")
                        if first_val != this_val:
                            # only string values can be merged (connected by '&&')
                            if isinstance(first_val, str):
                                new_val = first_val + "&&" + this_val
                                exec(f"merged_scene_properties.{scene_prop} = new_val")

                scene.scene_properties = merged_scene_properties
                # because ESA has some mess with the naming of their file names and
                # metadata, there might be duplicated seems not detected by the mapper
                # since the time stamps slightly differ (few seconds in some cases) but
                # their IDs are the same
                try:
                    scoll.add_scene(scene)
                except KeyError:
                    logger.warn(
                        f"Scene with ID {merged_scene_properties.product_uri} "
                        + f"already added to SceneCollection - continue"
                    )
                    continue
                update_scene_properties_list.append(merged_scene_properties)

            # update the metadata entries to avoid mis-matches in the number of
            # scenes and their URIs
            self.metadata.drop_duplicates(
                subset=[self.time_column], keep="first", inplace=True
            )
            for updated_scene_properties in update_scene_properties_list:
                # use the time stamp for finding the correct metadata records. There might be
                # some disagreement in the milliseconds because of different precision levels
                # therefore, an offset of less than 1 second is tolerated
                idx = self.metadata[
                    abs(
                        self.metadata[self.time_column]
                        - pd.to_datetime(updated_scene_properties.acquisition_time)
                    )
                    < pd.Timedelta(60, unit="minutes")
                ].index
                for scene_property in updated_scene_properties.__dict__:
                    self.metadata.loc[idx, scene_property] = eval(
                        f"updated_scene_properties.{scene_property}"
                    )

        # then add those scenes that are unique, i.e., no mosaicing is required
        if not _metadata_unique.empty:
            for _, item in _metadata_unique.iterrows():
                scene = self._process_scene(
                    item=item,
                    scene_constructor=scene_constructor,
                    scene_constructor_kwargs=scene_constructor_kwargs,
                    scene_modifier=scene_modifier,
                    scene_modifier_kwargs=scene_modifier_kwargs,
                    reprojection_method=reprojection_method,
                )
                # because ESA has some mess with the naming of their file names and
                # metadata, there might be duplicated seems not detected by the mapper
                # since the time stamps slightly differ (few seconds in some cases) but
                # their IDs are the same
                try:
                    scoll.add_scene(scene)
                except KeyError:
                    logger.warn(
                        f"Scene with ID {merged_scene_properties.product_uri} "
                        + f"already added to SceneCollection - continue"
                    )
                    continue

        # sort scenes by their timestamps and save as data attribute
        # to mapper instance
        self.data = scoll.sort()
        logger.info(f"Finished extraction of {self.sensor} scenes")

    def _load_pixels(
        self,
        pixel_reader: Optional[
            Callable[..., gpd.GeoDataFrame]
        ] = RasterCollection.read_pixels,
        pixel_reader_kwargs: Optional[Dict[str, Any]] = {},
    ) -> None:
        """
        Load pixel values from 0:N scenes into a `GeoDataFrame`

        :param pixel_reader:
            Callable to read the pixels from scenes. `RasterCollection.read_pixels` by
            default. Any other callable can be provided as long as it returns a
            GeoDataFrame and accepts `vector_features` and `fpath_raster` as input
            keyword arguments.
        :param pixel_reader_kwargs:
            optional keyword arguments to pass on to `pixel_reader`.
        """
        # loop over scenes and read the pixel values. Carry out reprojection where
        # necessary
        pixel_scene_list = []
        for _, item in self.metadata.iterrows():
            pixel_reader_kwargs.update(
                {
                    "vector_features": self.mapper_configs.feature.to_geoseries(),
                }
            )
            try:
                pixels = pixel_reader.__call__(item.real_path, **pixel_reader_kwargs)
                pixels[self.time_column] = item[self.time_column]
            except Exception as e:
                raise ValueError(f"Could not read pixel data: {e}")

            # reproject pixels if necessary
            pixels.to_crs(epsg=item.target_epsg, inplace=True)
            pixel_scene_list.append(pixels)

        self.data = pd.concat(pixel_scene_list)

    def load_scenes(
        self,
        scene_kwargs: Optional[Dict[str, Any]] = None,
        pixel_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Load scenes from `~Mapper.query_scenes` result into a `SceneCollection`
        (Polygon and MultiPolygon geometries) or into a `GeoDataFrame` (Point
        and MultiPoint geometries).

        Mosaicing operations are handled on the fly so calling programs will
        always receive analysis-ready data (e.g., when working across image
        tiles).

        :param scene_kwargs:
            key-word arguments to pass to `~Mapper._load_scenes_collection`
            for handling EOdal scenes. These arguments *MUST* be provided when
            using `Polygon` or `MulitPolygon` geometries in the `Mapper` call.
        :param pixel_kwargs:
            key-word arguments to pass to `~Mapper._load_pixels` for handling
            single pixel values. These arguments *MUST* be provided when
            using `Point` or `MulitPoint` geometries in the `Mapper` call.
        """
        # check if the correct keyword arguments have been passed
        if not self._geoms_are_points:
            if scene_kwargs is None:
                raise ValueError(
                    "Since Polygon/MultiPolygon geometries are provided "
                    + "`pixel_kwargs` must not be empty"
                )

        # check if scenes have been queried and found
        if self.metadata is None:
            warnings.warn(
                "No scenes are available - have you already executed Mapper.query_scenes()?"
            )
            return
        if self.metadata.empty:
            warnings.warn(
                "No scenes were found - consider modifying your search criteria"
            )
            return

        # check the spatial reference system of the scenes found. The mapper class
        # will ensure that all of them will be available in the same CRS. The CRS
        # is selected which most of the scenes already have to keep the reprojection
        # costs as small as possible (and also to avoid resampling induced errors)
        try:
            self.metadata["target_epsg"] = self.metadata.epsg.mode().values[0]
        except KeyError as e:
            raise ValueError(f"Could not determine CRS of scenes: {e}")

        # check if mosaicing scenes is required. This is done by checking the sensing_time
        # time stamps. If there are multiple scenes with the same time stamp they must be
        # mosaiced into a single scene
        self.metadata["mosaicing"] = False
        duplicated_idx = self.metadata[
            self.metadata.duplicated([self.time_column])
        ].index
        self.metadata.loc[duplicated_idx, "mosaicing"] = True

        # provide paths to raster data. Depending on th settings, this is a path on the
        # file system or a URL
        self.metadata["real_path"] = ""
        if settings.USE_STAC:
            self.metadata["real_path"] = self.metadata["assets"]
        else:
            self.metadata["real_path"] = self.metadata.apply(
                lambda x: reconstruct_path(record=x), axis=1
            )

        # load the data depending on the geometry type of the feature(s)
        if self._geoms_are_points:
            self._load_pixels(**pixel_kwargs)
        else:
            self._load_scenes_collection(**scene_kwargs)
