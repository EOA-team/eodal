"""
Mapping module for Sentinel-2 data

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

import os
import cv2
import geopandas as gpd
import numpy as np
import pandas as pd
import uuid

from datetime import date
from pathlib import Path
from shapely.geometry import box
from sqlalchemy.exc import DatabaseError
from typing import Any, Dict, List, Optional, Union

from eodal.config import get_settings
from eodal.core.sensors import Sentinel2
from eodal.metadata.sentinel2.database.querying import find_raw_data_by_bbox
from eodal.operational.mapping.mapper import Mapper, Feature
from eodal.operational.mapping.merging import merge_datasets
from eodal.operational.resampling.utils import identify_split_scenes
from eodal.utils.constants.sentinel2 import ProcessingLevels
from eodal.utils.exceptions import (
    InputError,
    BlackFillOnlyError,
    DataNotFoundError,
    STACError,
)
from eodal.metadata.sentinel2.utils import identify_updated_scenes
from eodal.metadata.utils import reconstruct_path
from eodal.core.scene import SceneProperties
from eodal.metadata.stac.client import sentinel2

settings = get_settings()
logger = settings.logger


class Sentinel2Mapper(Mapper):
    """
    Spatial mapping class for Sentinel-2 data.

    :attrib processing_level:
        Sentinel-2 data processing level (L1C or L2A)
    :attrib cloud_cover_threshold:
        global (scene-wide) cloud coverage threshold between 0 and 100% cloud cover.
        Scenes with cloud coverage reported higher than the threshold are discarded.
        To obtain *all* scenes in the archive use the default of 100%.
    :attrib use_latest_pdgs_baseline:
        since a scene can possible occur in different PDGS baseline numbers (the scene_id
        and product_uri will be different, which is supported by our data model)
        it is necessary to decide for a baseline in those cases where multiple scenes
        from the same sensing and data take time are available (originating from the
        same Sentinel-2 data but processed slightly differently). By default we use
        those scenes from the latest baseline. Otherwise, it is possible to use
        the baseline most scenes were processed with.
    """

    def __init__(
        self,
        processing_level: ProcessingLevels,
        cloud_cover_threshold: Optional[Union[int, float]] = 100,
        use_latest_pdgs_baseline: Optional[bool] = True,
        *args,
        **kwargs,
    ):
        """
        Initializes a new Sentinel-2 Mapper object

        :param processing_level:
            Sentinel-2 processing level to query
        :param cloud_cover_threshold:
            cloud cover threshold in percent (0-100%). Default is 100% to
            consider all scenes in the archive
        :param use_latest_pdgs_baseline:
            if True (default) forces *eodal* to use the latest processing
            baseline in case a scene is available in different processing levels
        :param tile_selection:
            optional list of Sentinel-2 tiles (e.g., ['T32TMT','T32TGM']) to use for
            filtering. Only scenes belonging to these tiles are returned then
        :param args:
            arguments to pass to the constructor of the ``Mapper`` super class
        :param kwargs:
            key-word arguments to pass to the constructor of the ``Mapper``
            super class
        """
        # initialize super-class
        Mapper.__init__(self, *args, **kwargs)

        object.__setattr__(self, "processing_level", processing_level)
        object.__setattr__(self, "cloud_cover_threshold", cloud_cover_threshold)
        object.__setattr__(self, "use_latest_pdgs_baseline", use_latest_pdgs_baseline)

    def get_scenes(self) -> None:
        """
        Queries the Sentinel-2 metadata DB for a selected time period and
        feature collection.

        NOTE:
            By passing a list of Sentinel-2 tiles you can explicitly control
            which Sentinel-2 tiles are considered. This might be useful for
            mapping tasks where your feature collection lies completely within
            a single Sentinel-2 tile but also overlaps with neighboring tiles.

        The scene selection and processing workflow contains several steps:

        1.  Query the metadata DB for **ALL** available scenes that overlap
            the bounding box of a given ``Polygon`` or ``MultiPolygon``
            feature. **IMPORTANT**: By passing a list of Sentinel-2 tiles
            to consider (``tile_ids``) you can explicitly control which
            Sentinel-2 tiles are considered!
        2.  Check if for a single sensing date several scenes are available
        3.  If yes check if that's due to Sentinel-2 data take or tiling grid
            design. If yes flag these scenes as potential merge candidates. A
            second reason for multiple scenes are differences in PDGS baseline,
            i.e., the dataset builds upon the **same** Sentinel-2 data but
            was processed by different base-line version.
        4.  If the scenes found have different spatial coordinate systems (CRS)
            (usually different UTM zones) flag the data accordingly. The target
            CRS is defined as that CRS the majority of scenes shares.
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

        s2_scenes = {}
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
            if settings.USE_STAC:
                try:
                    scenes_df = sentinel2(
                        date_start=self.date_start,
                        date_end=self.date_end,
                        processing_level=self.processing_level,
                        vector_features=bbox,
                        cloud_cover_threshold=self.cloud_cover_threshold,
                    )
                except Exception as e:
                    raise STACError(f"Querying STAC catalog failed: {e}")
            else:
                try:
                    scenes_df = find_raw_data_by_bbox(
                        date_start=self.date_start,
                        date_end=self.date_end,
                        processing_level=self.processing_level,
                        bounding_box=bbox,
                        cloud_cover_threshold=self.cloud_cover_threshold,
                    )
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
            s2_scenes[feature_uuid] = scenes_df

        # create feature collection
        features_gdf = pd.concat(features)
        # append raw scene count
        features_gdf["raw_scene_count"] = features_gdf.apply(
            lambda x, s2_scenes=s2_scenes: s2_scenes[x.name].shape[0], axis=1
        )
        features = features_gdf.__geo_interface__
        object.__setattr__(self, "observations", s2_scenes)
        object.__setattr__(self, "feature_collection", features)

    def _resample_s2_scene(self, s2_scene) -> None:
        """
        Resamples the Sentinel-2 into a user-defined spatial resolution

        :param s2_scene:
            `~eodal.core.sentinel2.Sentinel2` object with loaded S2
            data
        """
        # resample to target resolutionsorted_indices based on the MapperConfig settings
        has_scl = False
        band_selection = self.mapper_configs.band_names
        if band_selection is None:
            band_selection = s2_scene.band_names
        # make sure SCL is always resampled to 10m using nearest neighbor
        if "SCL" in band_selection:
            band_selection.remove("SCL")
            has_scl = True
        s2_scene.resample(
            band_selection=band_selection,
            interpolation_method=self.mapper_configs.resampling_method,
            target_resolution=self.mapper_configs.spatial_resolution,
            inplace=True,
        )
        if has_scl:
            s2_scene.resample(
                band_selection=["SCL"],
                interpolation_method=cv2.INTER_NEAREST_EXACT,
                target_resolution=self.mapper_configs.spatial_resolution,
                inplace=True,
            )

    def _read_multiple_scenes(
        self, scenes_date: pd.DataFrame, feature_gdf: gpd.GeoDataFrame, **kwargs
    ) -> Union[gpd.GeoDataFrame, Sentinel2]:
        """
        Backend method for processing and reading scene data if more than one scene
        is available for a given sensing date and feature (area of interest)

        :param scenes_date:
            `DataFrame` with all Sentinel-2 scenes of a single date
        :param feature_gdf:
            `GeoDataFrame` with spatial features for which to extract data
        :param kwargs:
            optional key-word arguments to pass on to
            `~eodal.core.sensors.Sentinel2.from_safe`
        """
        # check which baseline should be used
        return_highest_baseline = kwargs.get("return_highest_baseline", True)
        res = None
        # if the feature is a point we take the data set that is not blackfilled.
        # If more than one data set is not blackfilled  we simply take the
        # first data set
        if feature_gdf["geometry"].iloc[0].type == "Point":
            for _, candidate_scene in scenes_date.iterrows():
                if settings.USE_STAC:
                    in_dir = candidate_scene["assets"]
                else:
                    in_dir = candidate_scene["real_path"]
                feature_gdf = Sentinel2.read_pixels_from_safe(
                    point_features=feature_gdf,
                    in_dir=in_dir,
                    band_selection=self.mapper_configs.band_names,
                )
                # a empty data frame indicates black-fill
                if feature_gdf.empty:
                    continue
                res = feature_gdf
                res["sensing_date"] = candidate_scene["sensing_date"].values
                res["scene_id"] = candidate_scene["scene_id"].values
                break
        # in case of a (Multi-)Polygon: check if one of the candidate scenes complete
        # contains the feature (i.e., its bounding box). If that's the case and the
        # returned data is not black-filled, we can take that data set. If none of the
        # candidate contains the scene complete, merging and (depending on the CRS)
        # re-reprojection might be required. The result is then saved to disk in a temporary
        # directory.
        else:
            # check processing baseline first (one dataset can appear in different processing
            # baselines)
            updated_scenes, old_scenes = identify_updated_scenes(
                metadata_df=scenes_date, return_highest_baseline=return_highest_baseline
            )
            # only one scene left -> read the scene and return
            if updated_scenes.shape[0] == 1:
                if settings.USE_STAC:
                    in_dir = updated_scenes["assets"].iloc[0]
                else:
                    in_dir = updated_scenes["real_path"].iloc[0]
                # if there were only two input scenes we're done
                # otherwise we have to check if we have to merge data
                if scenes_date.shape[0] == 2:
                    res = Sentinel2.from_safe(
                        in_dir=in_dir,
                        band_selection=self.mapper_configs.band_names,
                        **kwargs,
                    )
                    self._resample_s2_scene(s2_scene=res)
                    return res
            # if updated scenes is not empty update the scenes_date DataFrame
            if not updated_scenes.empty:
                # drop "out-dated" scenes
                appended = pd.concat([scenes_date, old_scenes])
                appended.drop_duplicates(subset=['product_uri', 'tile_id'], keep=False, inplace=True)
                scenes_date = appended.copy()
                # if there is a single scene from a another tile in the
                # "old" scenes append it to the scenes_date
                old_scenes_grouped = old_scenes.groupby(by='tile_id')
                for tile_scenes in old_scenes_grouped:
                    if tile_scenes[0] not in scenes_date.tile_id.unique():
                        scenes_date = pd.concat(
                            [scenes_date, tile_scenes[1].copy()]
                        )

            # apply merge logic
            tmp_fnames = []
            scene_props = []
            for _, candidate_scene in scenes_date.iterrows():
                if settings.USE_STAC:
                    in_dir = candidate_scene["assets"]
                else:
                    in_dir = candidate_scene["real_path"]
                s2_scene = Sentinel2.from_safe(
                    in_dir=in_dir,
                    band_selection=self.mapper_configs.band_names,
                    **kwargs,
                )
                scene_props.append(s2_scene.scene_properties)
                self._resample_s2_scene(s2_scene=s2_scene)
                # reproject the scene if its CRS is not the same as the target_crs
                if (
                    s2_scene[s2_scene.band_names[0]].geo_info.epsg
                    != candidate_scene.target_crs
                ):
                    # make sure the pixel size remains the same after re-projection
                    # to do so, construct an explicit affine transformation matrix.
                    # Since all bands have the same spatial resolution this step can be
                    # applied to all bands at the same time
                    band = s2_scene.band_names[0]
                    nodata = s2_scene[band].nodata
                    geo_info_orig = s2_scene[band].geo_info
                    pixres_x_dst = abs(geo_info_orig.pixres_x)
                    pixres_y_dst = abs(geo_info_orig.pixres_y)
                    s2_scene.reproject(
                        band_selection=s2_scene.band_names,
                        target_crs=candidate_scene.target_crs,
                        dst_resolution=(pixres_x_dst, pixres_y_dst),
                        dst_nodata=nodata,
                        inplace=True,
                    )
                # write scene to temporary working directory and call rasterio.merge, returning
                # the merged dataset (save as tif to avoid compression issues)
                fname_scene = settings.TEMP_WORKING_DIR.joinpath(f"{uuid.uuid4()}.tif")
                s2_scene.to_rasterio(fname_scene)
                tmp_fnames.append(fname_scene)

            # merge datasets
            vector_features = kwargs.get("vector_features", None)
            band_options = {
                "band_names_dst": s2_scene.band_names,
                "band_aliases": s2_scene.band_aliases,
            }
            # adopt scene properties
            scene_dict = scene_props[0].__dict__
            scene_dict_keys = [x[1::] for x in scene_dict.keys()]
            scene_dict_vals = list(scene_dict.values())
            scene_dict = dict(zip(scene_dict_keys, scene_dict_vals))
            # combine product_uri's from the single datasets by '&'
            new_product_uri = "".join([x.product_uri + "&" for x in scene_props])[:-1]
            scene_dict.update({"product_uri": new_product_uri})
            scene_properties = SceneProperties(**scene_dict)

            try:
                res = merge_datasets(
                    datasets=tmp_fnames,
                    vector_features=vector_features,
                    band_options=band_options,
                    scene_properties=scene_properties,
                    sensor="sentinel2",
                )
            except Exception as e:
                raise ValueError(f"Could not merge Sentinel-2 datasets: {e}")
            # clean up working directory
            for tmp_fname in tmp_fnames:
                os.remove(tmp_fname)
        return res

    def get_observation(
        self, feature_id: Any, sensing_date: date, **kwargs
    ) -> Union[gpd.GeoDataFrame, Sentinel2, None]:
        """
        Returns the scene data (observations) for a selected feature and date.

        If for the date provided no scenes are found, the data from the scene(s)
        closest in time is returned

        :param feature_id:
            identifier of the feature for which to extract observations
        :param sensing_date:
            date for which to extract observations (or the closest date if
            no observations are available for the given date)
        :param kwargs:
            optional key-word arguments to pass on to
            `~eodal.core.sensors.Sentinel2.from_safe`
        :returns:
            depending on the geometry type of the feature either a
            ``GeoDataFrame`` (geometry type: ``Point``) or ``Sentinel2Handler``
            (geometry types ``Polygon`` or ``MultiPolygon``) is returned. if
            the observation contains nodata, only, None is returned.
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
            res = self._read_multiple_scenes(
                scenes_date=scenes_date, feature_gdf=feature_gdf, **kwargs
            )
            return res
        else:
            # determine scene path (local environment) or URLs (STAC)
            if settings.USE_STAC:
                in_dir = scenes_date["assets"].iloc[0]
            else:
                in_dir = scenes_date["real_path"].iloc[0]
            # if there is only one scene all we have to do is to read
            # read pixels in case the feature's dtype is point
            if feature_dict["features"][0]["geometry"]["type"] == "Point":
                res = Sentinel2.read_pixels_from_safe(
                    in_dir=in_dir,
                    band_selection=self.mapper_configs.band_names,
                    **kwargs,
                )
                res["sensing_date"] = scenes_date["sensing_date"].values
                res["scene_id"] = scenes_date["scene_id"].values
                return res
            # or the feature
            else:
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

    def get_complete_timeseries(
        self, feature_selection: Optional[List[Any]] = None,
        drop_blackfilled_scenes: Optional[bool] = True, **kwargs
    ) -> Dict[Any, Union[gpd.GeoDataFrame, List[Sentinel2]]]:
        """
        Extracts all observation with a time period for a feature collection.

        This function takes the Sentinel-2 scenes retrieved from the metadata DB query
        in `~Mapper.get_sentinel2_scenes` and extracts the Sentinel-2 data from the
        original .SAFE archives for all available scenes.

        :param feature_selection:
            optional subset of features ids (you can only select features included
            in the current feature collection)
        :param drop_blackfilled_scenes:
            drop scenes having no data values only (default)
        :param kwargs:
            optional key-word arguments to pass to `~eodal.core.band.Band.from_rasterio`
        """
        assets = {}
        # check if band selection is passed in kwargs
        band_selection_kwargs = kwargs.get('band_selection', None)
        if band_selection_kwargs is not None:
            object.__setattr__(self, 'band_names', band_selection_kwargs)
        # loop over features (AOIs) in feature dict
        for feature, scenes_df in self.observations.items():
            # in case a feature selection is available check if the current
            # feature is part of it
            if feature_selection is not None:
                if feature not in feature_selection:
                    continue

            # loop over scenes, they are already ordered by date (ascending)
            # and check for each date which scenes are relevant and require
            # potential reprojection or merging
            sensing_dates = scenes_df.sensing_date.unique()
            n_sensing_dates = len(sensing_dates)
            feature_res = []
            for idx, sensing_date in enumerate(sensing_dates):
                try:
                    res = self.get_observation(feature, sensing_date, **kwargs)
                    if drop_blackfilled_scenes:
                        if res.is_blackfilled:
                            logger.info(
                                f"Feature {feature}: "
                                f"Skipped data due to blackfill from {sensing_date} "
                                f"({idx+1}/{n_sensing_dates})"
                            )
                            continue
                    feature_res.append(res)
                    logger.info(
                        f"Feature {feature}: "
                        f"Extracted data from {sensing_date} "
                        f"({idx+1}/{n_sensing_dates})"
                    )
                except Exception as e:
                    logger.error(
                        f"Feature {feature}: "
                        f"Extracting data from {sensing_date} "
                        f"({idx+1}/{n_sensing_dates}) failed: {e}"
                    )
                    continue
            # if res is a GeoDataFrame the list can be concated
            if isinstance(res, gpd.GeoDataFrame):
                assets[feature] = pd.concat(feature_res)
            else:
                # order scenes by acquisition time
                timestamps = [x.scene_properties.acquisition_time for x in feature_res]
                sorted_indices = np.argsort(np.array(timestamps))
                feature_res_ordered = [feature_res[idx] for idx in sorted_indices]
                assets[feature] = feature_res_ordered
                
        return assets
