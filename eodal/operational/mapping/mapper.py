"""
Generic mapping module

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

import cv2
import geopandas as gpd
import pandas as pd
import uuid

from datetime import date
from geopandas import GeoDataFrame
from pandas import DataFrame
from pathlib import Path
from shapely.geometry import box, MultiPolygon, Point, Polygon
from sqlalchemy.exc import DatabaseError
from typing import Any, Dict, List, Optional, Tuple, Union

from eodal.config import get_settings
from eodal.core.raster import RasterCollection
from eodal.core.sensors import Sentinel1, Sentinel2
from eodal.metadata.stac import sentinel1, sentinel2
from eodal.metadata.utils import reconstruct_path
from eodal.metadata.sentinel1.database.querying import find_raw_data_by_bbox as \
    find_raw_data_by_bbox_sentinel1
from eodal.metadata.sentinel2.database.querying import find_raw_data_by_bbox as \
    find_raw_data_by_bbox_sentinel2
from eodal.operational.resampling.utils import identify_split_scenes
from eodal.operational.resampling.utils import identify_split_scenes
from eodal.utils.exceptions import BlackFillOnlyError, DataNotFoundError, InputError, \
    STACError

settings = get_settings()

class Feature(object):
    """
    Class representing a feature, e.g., an area of interest.

    :attrib identifier:
        unique identifier of the feature
    :attrib geom:
        geometry of the feature
    :attrib epsg:
        epsg code of the feature's geometry
    :attrib properties:
        any key-value dictionary like mapping of feature properties
        (e.g., its name or other attributes spoken in terms of an
        ESRI shapefile's table of attributes)
    """

    def __init__(
        self,
        identifier: Any,
        geom: Union[Point, Polygon, MultiPolygon],
        epsg: int,
        properties: Optional[Dict[str, Any]],
    ):
        """
        Initializes a new ``Feature`` instance.

        :param identifier:
            unique identifier of the feature
        :param geom:
            geometry of the feature
        :param epsg:
            epsg code of the feature's geometry
        :param properties:
            any key-value dictionary like mapping of feature properties
            (e.g., its name or other attributes spoken in terms of an
            ESRI shapefile's table of attributes)
        """
        # some checks
        if epsg <= 0:
            raise TypeError("EPSG codes must be >= 0")
        if not hasattr(geom, "__geo_interface__"):
            raise TypeError("Geometries must implement the __geo_interface__")
        if not isinstance(properties, dict):
            raise TypeError("Only dictionary are accepted")

        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "geom", geom)
        object.__setattr__(self, "epsg", epsg)
        object.__setattr__(self, "properties", properties)

    def __setattr__(self, *args):
        raise TypeError("Feature attributes are immutable")

    def __delattr__(self, *args):
        raise TypeError("Feature attributes are immutable")

    def __repr__(self):
        return str(self.__dict__)

    def to_gdf(self) -> GeoDataFrame:
        """
        Returns the feature as ``GeoDataFrame``

        :returns:
            ``Feature`` instance as ``GeoDataFrame``
        """
        self.properties.update({"epsg": self.epsg})
        return GeoDataFrame(
            self.properties,
            index=[self.identifier],
            crs=f"epsg:{self.epsg}",
            geometry=[self.geom],
        )

class MapperConfigs(object):
    """
    Class defining configurations for the ``Mapper`` class

    :attrib band_names:
        names of raster bands to process from each dataset found during the
        mapping process
    :attrib resampling_method:
        resampling might become necessary when the spatial resolution
        changes. Nearest neighbor by default.
    :attrib spatial_resolution:
        if provided brings all raster bands into the same spatial resolution
    :attrib reducers:
        optional list of spatial reducers (e.g., 'mean') converting all
        raster observations from 2d arrays to scalars.
    :atrrib tile_selection:
        optional selection of tile ids for sensors following a tiling scheme
        (e.g., S2 tiles, or Landsat PathRows).
    """

    def __init__(
        self,
        band_names: Optional[List[str]] = None,
        resampling_method: Optional[int] = cv2.INTER_NEAREST_EXACT,
        spatial_resolution: Optional[Union[int, float]] = 10.0,
        reducers: Optional[List[str]] = None,
        tile_selection: Optional[List[str]] = None,
    ):
        """
        Constructs a new ``MapperConfig`` instance.

        :param band_names:
            names of raster bands to process from each dataset found during the
            mapping process
        :param resampling_method:
            resampling might become necessary when the spatial resolution
            changes. Nearest neighbor by default.
        :param spatial_resolution:
            if provided brings all raster bands into the same spatial resolution
        :param reducers:
            optional list of spatial reducers (e.g., 'mean') converting all
            raster observations from 2d arrays to scalars.
        """
        object.__setattr__(self, "band_names", band_names)
        object.__setattr__(self, "resampling_method", resampling_method)
        object.__setattr__(self, "spatial_resolution", spatial_resolution)
        object.__setattr__(self, "reducers", reducers)
        object.__setattr__(self, "tile_selection", tile_selection)

    def __setattr__(self, *args):
        raise TypeError("MapperConfigs attributes are immutable")

    def __delattr__(self, *args):
        raise TypeError("MapperConfigs attributes are immutable")

    def __repr__(self):
        return str(self.__dict__)

class Mapper(object):
    """
    Generic Mapping class to extract raster data for a selection of areas of interest
    (AOIs) and time period.

    :attrib date_start:
        start date of the time period to consider (inclusive)
    :attrib date_end:
        end date of the time period to consider (inclusive)
    :attrib feature_collection:
        ``GeoDataFrame`` or any vector file understood by ``fiona`` with
        geometries of type ``Point``, ``Polygon`` or ``MultiPolygon``
        defining the Areas Of Interest (AOIs) to extract (e.g., agricultural
        field parcels). Each feature in the collection will be processed
        separately
    :attrib unique_id_attribute:
        attribute in the `polygon_features`'s attribute table making each
        feature (AOI) uniquely identifiable. If None (default) the features
        are labelled by a unique-identifier created on the fly.
    :attrib mapping_configs:
        Mapping configurations specified by `~eodal.operational.mapping.MapperConfigs`.
        Uses default configurations if not provided.
    :attrib observations:
        data structure for storing DB query results per AOI.
    """

    def __init__(
        self,
        date_start: date,
        date_end: date,
        feature_collection: Union[Path, GeoDataFrame],
        unique_id_attribute: Optional[str] = None,
        mapper_configs: MapperConfigs = MapperConfigs(),
        collection: Optional[str] = ''
    ):
        """
        Constructs a new ``Mapper`` instance.

        :param date_start:
            start date of the time period to consider (inclusive)
        :param date_end:
            end date of the time period to consider (inclusive)
        :param feature_collection:
            ``GeoDataFrame`` or any vector file understood by ``fiona`` with
            geometries of type ``Point``, ``Polygon`` or ``MultiPolygon``
            defining the Areas Of Interest (AOIs) to extract (e.g., agricultural
            field parcels). Each feature in the collection will be processed
            separately
        :param unique_id_attribute:
            attribute in the `polygon_features`'s attribute table making each
            feature (AOI) uniquely identifiable. If None (default) the features
            are labelled by a unique-identifier created on the fly.
        :param mapping_configs:
            Mapping configurations specified by `~eodal.operational.mapping.MapperConfigs`.
            Uses default configurations if not provided.
        """
        object.__setattr__(self, "date_start", date_start)
        object.__setattr__(self, "date_end", date_end)
        object.__setattr__(self, "feature_collection", feature_collection)
        object.__setattr__(self, "unique_id_attribute", unique_id_attribute)
        object.__setattr__(self, "mapper_configs", mapper_configs)
        object.__setattr__(self, "collection", collection)

        observations: Dict[str, DataFrame] = None
        object.__setattr__(self, "observations", observations)

        features: Dict[str, Feature] = None
        object.__setattr__(self, "features", features)

    def __setattr__(self, *args):
        raise TypeError("Mapper attributes are immutable")

    def __delattr__(self, *args):
        raise TypeError("Mapper attributes are immutable")

    def _get_scenes(self, sensor: str) -> None:
        """
        Method to query available scenes. Works sensor-agnostic but requires a
        sensor to be specified to select the correct metadata queries

        :param sensor:
            name of the sensor for which to search for scenes
        """
        # prepare features
        aoi_features = self._prepare_features()

        scenes = {}
        # features implement the __geo_interface__
        features = []
        # extract all properties from the input features to preserve them
        cols_to_ignore = [self.unique_id_attribute, "geometry", "geometry_wgs84"]
        property_columns = [x for x in aoi_features.columns if x not in cols_to_ignore]
        for _, feature in aoi_features.iterrows():

            feature_uuid = feature[self.unique_id_attribute]
            properties = feature[property_columns].to_dict()
            feature_obj = Feature(
                identifier=feature_uuid,
                geom=feature["geometry"],
                epsg=aoi_features.crs.to_epsg(),
                properties=properties,
            )
            features.append(feature_obj.to_gdf())

            # determine bounding box of the current feature using
            # its representation in geographic coordinates
            bbox = box(*feature.geometry_wgs84.bounds)

            # use the resulting bbox to query the bounding box
            # there a two options: use STAC or the PostgreSQL DB
            # prepare sensor specific kwargs
            kwargs = {
                'date_start': self.date_start,
                'date_end': self.date_end,
                'vector_features': bbox
            }
            if sensor.lower() == 'sentinel2':
                kwargs.update({
                    'processing_level': self.processing_level,
                    'cloud_cover_threshold': self.cloud_cover_threshold
                })
            elif sensor.lower() == 'sentinel1':
                kwargs.update({
                    'collection': self.collection
                })

            if settings.USE_STAC:
                try:
                    scenes_df = eval(f'{sensor}(**kwargs)')
                except Exception as e:
                    raise STACError(f"Querying STAC catalog failed: {e}")
            else:
                try:
                    scenes_df = eval(f'find_raw_data_by_bbox_{sensor}(**kwargs)')
                except Exception as e:
                    raise DatabaseError(f"Querying metadata DB failed: {e}")

            # filter by tile if required
            tile_ids = self.mapper_configs.tile_selection
            if tile_ids is not None:
                other_tile_idx = scenes_df[~scenes_df.tile_id.isin(tile_ids)].index
                scenes_df.drop(other_tile_idx, inplace=True)

            if scenes_df.empty:
                raise UserWarning(
                    f"The query for feature {feature_uuid} returned now results"
                )
                continue

            # check if the satellite data is in different projections
            in_single_crs = scenes_df.epsg.unique().shape[0] == 1

            # check if there are several scenes available for a single sensing date
            # in this case merging of different datasets might be necessary
            scenes_df_split = identify_split_scenes(scenes_df)
            scenes_df["is_split"] = False

            if not scenes_df_split.empty:
                scenes_df.loc[
                    scenes_df.product_uri.isin(scenes_df_split.product_uri), "is_split"
                ] = True

            # in case the scenes have different projections (most likely different UTM
            # zone numbers) figure out which will be target UTM zone. To avoid too many
            # reprojection operations of raster data later, the target CRS is that CRS
            # most scenes have (expressed as EPSG code)
            scenes_df["target_crs"] = scenes_df.epsg
            if not in_single_crs:
                most_common_epsg = scenes_df.epsg.mode().values
                scenes_df.loc[
                    ~scenes_df.epsg.isin(most_common_epsg), "target_crs"
                ] = most_common_epsg[0]

            # add the scenes_df DataFrame to the dictionary that contains the data for
            # all features
            scenes[feature_uuid] = scenes_df

        # create feature collection
        features_gdf = pd.concat(features)
        # append raw scene count
        features_gdf["raw_scene_count"] = features_gdf.apply(
            lambda x, scenes=scenes: scenes[x.name].shape[0], axis=1
        )
        features = features_gdf.__geo_interface__
        object.__setattr__(self, "observations", scenes)
        object.__setattr__(self, "feature_collection", features)

    def _prepare_features(self) -> pd.DataFrame:
        """
        Prepares the feature collection for mapping

        :returns:
            `DataFrame` with prepared features
        """
        # read features and loop over them to process each feature separately
        is_file = isinstance(self.feature_collection, Path) or isinstance(
            self.feature_collection, str
        )
        if is_file:
            try:
                aoi_features = gpd.read_file(self.feature_collection)
            except Exception as e:
                raise InputError(
                    f"Could not read polygon features from file "
                    f"{self.feature_collection}: {e}"
                )
        else:
            aoi_features = self.feature_collection.copy()

        # for the DB query, the geometries are required in geographic coordinates
        # however, we keep the original coordinates as well to avoid to many reprojections
        aoi_features["geometry_wgs84"] = aoi_features["geometry"].to_crs(4326)

        # check if there is a unique feature column
        # otherwise create it using uuid
        if self.unique_id_attribute is not None:
            if not aoi_features[self.unique_id_attribute].is_unique:
                raise ValueError(
                    f'"{self.unique_id_attribute}" is not unique for each feature'
                )
        else:
            object.__setattr__(self, "unique_id_attribute", "_uuid4")
            aoi_features[self.unique_id_attribute] = [
                str(uuid.uuid4()) for _ in aoi_features.iterrows()
            ]
        return aoi_features

    def get_feature_ids(self) -> List:
        """
        Lists feature identifiers in feature collection

        :returns:
            list of feature identifiers
        """
        if isinstance(self.feature_collection, Path):
            return []
        return [x["id"] for x in self.feature_collection["features"]]

    def get_feature(self, feature_id: Any) -> Dict[str, Any]:
        """
        Returns a feature in its ``__geo_interface__`` representation
        out of the feature collection

        :param feature_id:
            feature identifier to use for extraction
        :param as_gdf:
            return feature as dictionary (default) or ``GeoDataFrame``?
        :returns:
            the feature with its properties and geometry
        """
        if isinstance(self.feature_collection, Path):
            return {}
        if isinstance(self.feature_collection, GeoDataFrame):
            gdf = self.feature_collection[
                self.feature_collection[self.unique_id_attribute] == feature_id
            ]
            return {} if gdf.empty else gdf.__geo_interface__
        else:
            res = [
                x for x in self.feature_collection["features"] if x["id"] == feature_id
            ]
            if len(res) == 0:
                raise KeyError(f'No feature found with ID "{feature_id}"')
            return {"type": "FeatureCollection", "features": res}

    def get_feature_scenes(self, feature_identifier: Any) -> DataFrame:
        """
        Returns a ``DataFrame`` with all scenes found for a
        feature in the feature collection

        NOTE:
            The scene count is termed ``raw_scene_count``. This
            highlights that the final scene count might be
            different due to orbit and spatial design pattern.

        :param feature_identifier:
            unique identifier of the aoi. Must be the same identifier
            used during the database query
        :returns:
            ``DataFrame`` with all scenes found for a given
            set of search parameters
        """
        try:
            return self.observations[feature_identifier].copy()
        except Exception as e:
            raise KeyError(f"{feature_identifier} did not return any results: {e}")

    def _get_observation(
        self, feature_id: Any, sensing_date: date, sensor: str, **kwargs
    ) -> Union[gpd.GeoDataFrame, RasterCollection, Tuple,  None]:
        """
        Returns the scene data (observations) for a selected feature and date.

        If for the date provided no scenes are found, the data from the scene(s)
        closest in time is returned

        :param feature_id:
            identifier of the feature for which to extract observations
        :param sensing_date:
            date for which to extract observations (or the closest date if
            no observations are available for the given date)
        :param sensor:
            name of the sensor for which to extract the observation.
        :param kwargs:
            optional key-word arguments to pass on to
            `~eodal.core.sensors` class-specific methods
        :returns:
            depending on the geometry type of the feature either a
            ``GeoDataFrame`` (geometry type: ``Point``) or ``Sentinel2Handler``
            (geometry types ``Polygon`` or ``MultiPolygon``) is returned. if
            the observation contains nodata, only, None is returned. If multiple
            scenes must be read to get a single observation, the status 'multiple'
            is returned.
        """
        # define variable for returning results
        res = None
        # get available observations for the AOI feature
        scenes_df = self.observations.get(feature_id, None)
        if scenes_df is None:
            raise DataNotFoundError(
                f'Could not find any scenes for feature with ID "{feature_id}"'
            )

        # get scene(s) closest to the sensing_date provided
        min_delta = abs((scenes_df.sensing_date - sensing_date)).min()
        scenes_date = scenes_df[
            abs((scenes_df.sensing_date - sensing_date)) == min_delta
        ].copy()

        # map the dataset path(s) when working locally (no STAC)
        if not settings.USE_STAC:
            try:
                scenes_date["real_path"] = scenes_date.apply(
                    lambda x: reconstruct_path(record=x), axis=1
                )
            except Exception as e:
                raise DataNotFoundError(
                    f"Cannot find the scenes on the file system: {e}"
                )
        # get properties and geometry of the current feature from the collection
        feature_dict = self.get_feature(feature_id)
        feature_gdf = gpd.GeoDataFrame.from_features(feature_dict)
        feature_gdf.crs = feature_dict["features"][0]["properties"]["epsg"]
        # parse feature geometry in kwargs so that only a spatial subset is read
        # in addition parse the S2 gain factor as "scale" argument
        kwargs.update({"vector_features": feature_gdf})
        # multiple scenes for a single date
        # check what to do (re-projection, merging)
        if scenes_date.shape[0] > 1:
            return ('multiple', scenes_date, feature_gdf)
        else:
            # determine scene path (local environment) or URLs (STAC)
            if settings.USE_STAC:
                in_dir = scenes_date["assets"].iloc[0]
            else:
                in_dir = scenes_date["real_path"].iloc[0]
            # if there is only one scene all we have to do is to read
            # read pixels in case the feature's dtype is point
            if feature_dict["features"][0]["geometry"]["type"] == "Point":
                if sensor.lower() == 'sentinel1':
                    res = Sentinel1.read_pixels_from_safe(
                        in_dir=in_dir,
                        polarizations=self.mapper_configs.band_names,
                        **kwargs
                    )
                elif sensor.lower() == 'sentinel2':
                    res = Sentinel2.read_pixels_from_safe(
                        in_dir=in_dir,
                        band_selection=self.mapper_configs.band_names,
                        **kwargs,
                    )
                res["sensing_date"] = scenes_date["sensing_date"].values
                res["scene_id"] = scenes_date["scene_id"].values
            # or the feature
            else:
                if sensor.lower() == 'sentinel1':
                    try:
                        res = Sentinel1.from_safe(
                            in_dir=in_dir,
                            band_selection=self.mapper_configs.band_names,
                            **kwargs
                        )
                    except Exception as e:
                        raise Exception from e
                elif sensor.lower() == 'sentinel2':
                    try:
                        res = Sentinel2.from_safe(
                            in_dir=in_dir,
                            band_selection=self.mapper_configs.band_names,
                            **kwargs,
                        )
                        self._resample_s2_scene(s2_scene=res)
                    except BlackFillOnlyError:
                        return res
                    except Exception as e:
                        raise Exception from e
        return res
