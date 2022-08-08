'''
Vector geometry operations.
'''

import geopandas as gpd
import json

from shapely.geometry import box

def box_to_geojson(gdf: gpd.GeoDataFrame) -> str:
    """
    Casts the bounding box of a `GeoDataFrame` to GeoJson

    :param gdf:
        Non-empty `GeoDataFrame`
    :returns:
        `total_bounds` of gpd in GeoJson notation
    """
    # GeoJSON should be in geographic coordinates
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    bbox = gdf_wgs84.total_bounds
    bbox_poly = box(*bbox)
    bbox_json = gpd.GeoSeries([bbox_poly]).to_json()
    return json.loads(bbox_json)['features'][0]['geometry']
