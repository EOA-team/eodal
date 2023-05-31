if __name__ == "__main__":

    # some testing -> to be moved to tests later
    import geopandas as gpd

    from datetime import datetime
    from eodal.core.sensors import Landsat
    from eodal.mapper.feature import Feature
    from eodal.mapper.filter import Filter
    from eodal.metadata.stac.client import landsat
    from shapely.geometry import box

    # query STAC for a custom region
    collection = 'landsat-c2-l2'
    bbox = box(*[7.0, 47.0, 8.0, 48.0])
    feature = Feature(
        name='landsat-test',
        geometry=bbox,
        epsg=4326,
        attributes={})
    time_start = datetime(2023, 5, 1)
    time_end = datetime(2023, 5, 30)

    metadata_filters = [
        Filter('eo:cloud_cover', '<', 70),
        Filter('instruments', '==', 'oli')
    ]

    landsat_items = landsat(
        metadata_filters=metadata_filters,
        collection='landsat-c2-l2',
        bounding_box=bbox,
        time_start=time_start,
        time_end=time_end)

    # read only a part of the test scene
    landsat_scene_item = landsat_items.iloc[0]
    gdf = gpd.GeoSeries([bbox], crs=4326)
    landsat = Landsat.from_usgs(
        in_dir=landsat_scene_item['assets'],
        vector_features=gdf,
        read_qa=False,
        read_atcor=False
    )

    # get a complete test scene
    landsat = Landsat.from_usgs(
        in_dir=landsat_scene_item['assets'],
        band_selection=['blue', 'green', 'red']
    )