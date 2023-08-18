"""
Querying datasets from a Spatio-Temporal Asset Catalog (STAC).
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import warnings

from datetime import datetime
from pystac_client import Client
from pystac_client.stac_api_io import StacApiIO
from requests.adapters import HTTPAdapter, Retry
from shapely.geometry import box, Polygon
from typing import Any, Dict, List

from eodal.config import get_settings, STAC_Providers
from eodal.mapper.filter import Filter
from eodal.utils.decorators import prepare_bbox
from eodal.utils.geometry import box_from_transform, prepare_gdf
from eodal.utils.reprojection import infer_utm_zone
from eodal.utils.timestamps import datetime_to_date

Settings = get_settings()


def query_stac(
    time_start: datetime,
    time_end: datetime,
    collection: str,
    bounding_box: Polygon,
) -> List[Dict[str, Any]]:
    """
    Queries a STAC (Spatio-Temporal Asset Catalog) by bounding box and
    time period to get items from a user-defined collection.

    This is a sensor-agnostic function called by sensor-specific ones.

    :param time_start:
        start of the time period
    :param time_end:
        end of the time period
    :param collection:
        name of the collection
        (e.g., sentinel-2-l2a for Sentinel-2 L2A data)
    :param bounding_box:
        bounding box either as extended well-known text in geographic coordinates
        or as shapely ``Polygon`` in geographic coordinates (WGS84)
    :returns:
        list of dictionary items returned from the STAC query
    """
    # open connection to STAC server (specify custom CA_BUNDLE if required)
    stac_api_io = StacApiIO()

    # ..versionadd:: 0.2.1
    # add retries in case of HTTP 502, 503 and 504 errors
    # TODO pass `Retry` object to `StacApiIO` with python >= 3.8
    # and `pystac-client` >= 0.7.0.
    retries = Retry(
        total=Settings.NUMBER_HTTPS_RETRIES,
        backoff_factor=1,
        status_forcelist=[502, 503, 504])
    stac_api_io.session.mount("http://", HTTPAdapter(max_retries=retries))
    stac_api_io.session.mount("https://", HTTPAdapter(max_retries=retries))

    # handle certificate bundle
    stac_api_io.session.verify = Settings.STAC_API_IO_CA_BUNDLE

    # setup the client
    cat = Client.from_file(Settings.STAC_BACKEND.URL, stac_io=stac_api_io)

    # transform dates into the required format (%Y-%m-%d)
    datestr = f'{time_start.strftime("%Y-%m-%d")}/{time_end.strftime("%Y-%m-%d")}'
    # search datasets on catalog
    search = cat.search(
        collections=collection,
        intersects=bounding_box,
        datetime=datestr,
        max_items=Settings.MAX_ITEMS,
        limit=Settings.LIMIT_ITEMS,
    )
    # fetch items and convert them to GeoDataFrame, drop all records with
    # too many clouds
    items = search.item_collection()
    item_json = items.to_dict()
    scenes = item_json["features"]
    return scenes


def _filter_criteria_fulfilled(
    metadata_dict: Dict[str, Any], metadata_filters: List[Filter]
) -> bool:
    """
    Check if a scene fulfills the metadata filter criteria

    :param metadata_dict:
        scene metadata returned from STAC item
    :param metadata_filters:
        scene metadata filters to apply on metadata_dict
    :returns:
        `True` if all criteria passed, `False` if a single
        criterion was not met.
    """
    criteria_fulfilled = []
    for _filter in metadata_filters:
        if _filter.entity in ["processing_level", "product_type"]:
            continue
        if _filter.entity not in metadata_dict.keys():
            warnings.warn(
                f"{_filter.entity} could not be retrieved from STAC -> skipping filter"
            )
        # check if the filter condition is met
        # check if the metadata item to filter is a list or single value
        if not isinstance(metadata_dict[_filter.entity], list):
            if isinstance(metadata_dict[_filter.entity], str):
                eval_str = \
                    f'metadata_dict["{_filter.entity}"] ' + \
                    f'{_filter.operator} "{_filter.value}"'
            else:
                eval_str = \
                    f'metadata_dict["{_filter.entity}"] ' + \
                    f'{_filter.operator} {_filter.value}'
            condition_met = eval(eval_str)
        else:
            # TODO: this is not really elegant and might not deliver always the
            # results we are looking for ...
            # convert _filter.value to list if it is not yet
            value = _filter.value
            if not isinstance(value, list):
                value = [value]
            # redefine the operators to work with sets
            if _filter.operator == '==':
                condition_met = set(value).issubset(metadata_dict[_filter.entity])
            elif _filter.operator == '!=':
                condition_met = not set(value).issubset(metadata_dict[_filter.entity])
        criteria_fulfilled.append(condition_met)

    return all(criteria_fulfilled)


@prepare_bbox
def sentinel2(metadata_filters: List[Filter], **kwargs) -> gpd.GeoDataFrame:
    """
    Sentinel-2 specific STAC query allows filtering by scene-wide cloudy pixel
    percentage.

    :param metadata_filters:
        custom filters for filtering scenes in catalog by some metadata attributes
    :param kwargs:
        keyword arguments to pass to `query_stac` function
    :returns:
        dataframe with references to found Sentinel-2 scenes
    """
    # check for processing level of the data and set the collection accordingly
    filter_entities = [x.entity for x in metadata_filters]
    if "processing_level" in filter_entities:
        processing_level = [
            x.value for x in metadata_filters if x.entity == "processing_level"
        ][0]
        processing_level = processing_level.replace("-", "_")
    processing_level_stac = eval(f"Settings.STAC_BACKEND.S2{processing_level}")
    kwargs.update({"collection": processing_level_stac})

    # query STAC catalog
    stac_kwargs = kwargs.copy()
    scenes = query_stac(**stac_kwargs)

    # get STAC provider specific naming conventions
    s2 = Settings.STAC_BACKEND.Sentinel2
    # loop over scenes found and apply the Filters provided
    metadata_list = []
    for scene in scenes:
        # extract scene metadata required for Sentinel-2
        # map the STAC keys to eodal's naming convention
        props = scene["properties"]
        # tile-id requires some string handling in case of AWS
        if isinstance(s2.tile_id, list):
            tile_id = "".join(
                [str(props[x]) for x in Settings.STAC_BACKEND.Sentinel2.tile_id]
            )
        else:
            tile_id = props[Settings.STAC_BACKEND.Sentinel2.tile_id]
        # the product_uri is also not handled the same way by the different
        # STAC providers
        try:
            product_uri = scene[s2.product_uri]
        except KeyError:
            product_uri = props[s2.product_uri]
        # same for the scene_id
        try:
            scene_id = props[s2.scene_id]
        except KeyError:
            scene_id = scene[s2.scene_id]
        # TODO: think about a more generic way to do this. The problem is:
        # we need to map the different STAC provider settings into EOdals
        # metadata model to avoid having the user to think about it
        meta_dict = {
            "product_uri": product_uri,
            "scene_id": scene_id,
            "spacecraft_name": props[s2.platform],
            "tile_id": tile_id,
            "sensing_date": datetime_to_date(props[s2.sensing_time]),
            "cloudy_pixel_percentage": props[s2.cloud_cover],
            "epsg": props[s2.epsg],
            "sensing_time": datetime.strptime(
                props[s2.sensing_time], s2.sensing_time_fmt
            ),
            "sun_azimuth_angle": props[s2.sun_azimuth_angle],
            "sun_zenith_angle": props[s2.sun_zenith_angle],
            "geom": Polygon(scene["geometry"]["coordinates"][0]),
        }
        # get links to actual Sentinel-2 bands
        meta_dict["assets"] = scene["assets"]

        # apply filters
        append_scene = _filter_criteria_fulfilled(meta_dict, metadata_filters)
        if append_scene:
            metadata_list.append(meta_dict)

    # create geppandas GeoDataFrame out of scene metadata records
    return prepare_gdf(metadata_list)


@prepare_bbox
def sentinel1(metadata_filters: List[Filter], **kwargs) -> gpd.GeoDataFrame:
    """
    Sentinel-1 specific STAC query function to retrieve mapper from MSPC.

    IMPORTANT:
        Returns the RTC product by default if not stated otherwise (using
        `EOdal.mapper.filter` on `product_type`

    :param metadata_filters:
        custom filters for filtering scenes in catalog by some metadata attributes
    :param kwargs:
        :param kwargs:
        keyword arguments to pass to `query_stac` function
    :returns:
        dataframe with references to found Sentinel-1 scenes
    """

    if Settings.STAC_BACKEND != STAC_Providers.MSPC:
        raise ValueError("This method currently requires Microsoft Planetary Computer")

    # construct collection string (defaults to S1RTC if not stated otherwise in the
    # metadata filters)
    collection = "S1"
    if len([x.entity for x in metadata_filters if x.entity == "product_type"]) == 1:
        collection += [x.value for x in metadata_filters if x.entity == "product_type"][
            0
        ]
    else:
        collection += "RTC"

    # query the catalog
    stac_kwargs = kwargs.copy()
    stac_kwargs.update({"collection": eval(f"Settings.STAC_BACKEND.{collection}")})
    scenes = query_stac(**stac_kwargs)
    metadata_list = []
    for scene in scenes:
        metadata_dict = scene["properties"]
        metadata_dict["assets"] = scene["assets"]
        metadata_dict["sensing_time"] = metadata_dict["datetime"]
        metadata_dict["sensing_date"] = datetime_to_date(metadata_dict['sensing_time'])
        del metadata_dict["datetime"]
        # infer EPSG code of the scene in UTM coordinates from its bounding box
        bbox = box(*scene["bbox"])
        metadata_dict["epsg"] = infer_utm_zone(bbox)
        metadata_dict["geom"] = bbox
        # apply filters
        append_scene = _filter_criteria_fulfilled(metadata_dict, metadata_filters)
        if append_scene:
            metadata_list.append(metadata_dict)

    # create geppandas GeoDataFrame out of scene metadata records
    return prepare_gdf(metadata_list)


@prepare_bbox
def landsat(metadata_filters: List[Filter], **kwargs) -> gpd.GeoDataFrame:
    """
    Landsat specific STAC query function to retrieve mapper from MSPC.

    :param metadata_filters:
        custom filters for filtering scenes in catalog by some metadata attributes
    :param kwargs:
        :param kwargs:
        keyword arguments to pass to `query_stac` function
    :returns:
        dataframe with references to found Landsat scenes
    """

    if Settings.STAC_BACKEND != STAC_Providers.MSPC:
        raise ValueError("This method currently requires Microsoft Planetary Computer")

    # query the catalog
    stac_kwargs = kwargs.copy()
    scenes = query_stac(**stac_kwargs)

    if len(scenes) == 0:
        raise ValueError(f'STAC query returned no results! {stac_kwargs}')

    metadata_list = []
    for scene in scenes:
        metadata_dict = scene['properties']
        metadata_dict['assets'] = scene['assets']
        metadata_dict["sensing_time"] = metadata_dict["datetime"]
        metadata_dict["sensing_date"] = datetime_to_date(metadata_dict['sensing_time'])
        del metadata_dict["datetime"]
        # apply filters
        append_scene = _filter_criteria_fulfilled(metadata_dict, metadata_filters)
        if append_scene:
            metadata_list.append(metadata_dict)
        # reconstruct the scene footprint
        transform = metadata_dict['proj:transform']
        shape = metadata_dict['proj:shape']
        metadata_dict['geom'] = box_from_transform(transform, shape)
        metadata_dict['epsg'] = metadata_dict['proj:epsg']

        # extract angles
        metadata_dict['sun_azimuth_angle'] = metadata_dict['view:sun_azimuth']
        del metadata_dict['view:sun_azimuth']
        metadata_dict['sun_zenith_angle'] = 90. - metadata_dict['view:sun_elevation']
        del metadata_dict['view:sun_elevation']
        metadata_dict['sensor_zenith_angle'] = metadata_dict['view:off_nadir']
        del metadata_dict['view:off_nadir']

    if len(metadata_list) == 0:
        raise ValueError(
            f'No scenes fulfilling filter criteria: {metadata_filters}')
    return prepare_gdf(metadata_list)
    