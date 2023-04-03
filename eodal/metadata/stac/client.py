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
from shapely.geometry import box, Polygon
from typing import Any, Dict, List

from eodal.config import get_settings, STAC_Providers
from eodal.mapper.filter import Filter
from eodal.utils.decorators import prepare_bbox
from eodal.utils.reprojection import infer_utm_zone

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
    stac_api_io.session.verify = Settings.STAC_API_IO_CA_BUNDLE
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
    items = search.get_all_items()
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
    criteria_fulfilled = True
    for filter in metadata_filters:
        if filter.entity in ["processing_level", "product_type"]:
            continue
        if filter.entity not in metadata_dict.keys():
            warnings.warn(
                f"{filter.entity} could not be retrieved from STAC -> skipping filter"
            )
        # check if the filter condition is met
        condition_met = eval(
            f'metadata_dict["{filter.entity}"] {filter.operator} {filter.value}'
        )
        if not condition_met:
            criteria_fulfilled = False
            break
    return criteria_fulfilled


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
    del stac_kwargs["platform"]
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
            "sensing_date": datetime.strptime(
                props[s2.sensing_time].split("T")[0], "%Y-%m-%d"
            ).date(),
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
    df = pd.DataFrame(metadata_list)
    df.sort_values(by="sensing_time", inplace=True)
    return gpd.GeoDataFrame(df, geometry="geom", crs=4326)


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
    del stac_kwargs["platform"]
    stac_kwargs.update({"collection": eval(f"Settings.STAC_BACKEND.{collection}")})
    scenes = query_stac(**stac_kwargs)
    metadata_list = []
    for scene in scenes:
        metadata_dict = scene["properties"]
        metadata_dict["assets"] = scene["assets"]
        metadata_dict["sensing_time"] = metadata_dict["datetime"]
        metadata_dict["sensing_date"] = datetime.strptime(
            metadata_dict["sensing_time"].split("T")[0], "%Y-%m-%d"
        ).date()
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
    df = pd.DataFrame(metadata_list)
    df.sort_values(by="sensing_time", inplace=True)
    return gpd.GeoDataFrame(df, geometry="geom", crs=4326)
