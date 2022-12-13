'''
Created on Nov 24, 2022

@author: graflu
'''

import pytest
import datetime
import geopandas as gpd
import matplotlib.pyplot as plt
import random
import xarray as xr

from datetime import date
from shapely.geometry import Point, Polygon
from typing import List

from eodal.core.band import Band
from eodal.core.raster import RasterCollection
from eodal.core.scene import SceneCollection
from eodal.core.sensors import Sentinel2

@pytest.fixture()
def generate_random_points():
    def _generate_random(number: int, polygon: Polygon) -> List[Point]:
        """
        Generates random points within a polygon
    
        :param number:
            number of random points to create
        :param polygon:
            polygon within to sample the points
        :returns:
            list of randomly sampled points within the polygon bounds
        """
        points = []
        minx, miny, maxx, maxy = polygon.bounds
        while len(points) < number:
            pnt = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
            if polygon.contains(pnt):
                points.append(pnt)
        return points
    return _generate_random

def test_raster_is_scene(get_bandstack):
    """test the is_scene attribute of RasterCollections"""

    fpath_raster = get_bandstack()
    ds = RasterCollection.from_multi_band_raster(
        fpath_raster=fpath_raster
    )
    assert not ds.is_scene, 'scene metadata have not been set, so it is not a scene'

    ds.scene_properties.acquisition_time = 2000
    ds.scene_properties.platform = 'test'
    assert ds.is_scene, 'scene metadata have been set, so it is a scene'

def test_scene_collection(get_s2_safe_l2a, get_polygons_2, get_bandstack):
    """test scene collection constructor calls and built-ins"""

    # prepare inputs
    polys = get_polygons_2()
    fpath_s2 = get_s2_safe_l2a()
    # read the scene two times so that we can "fake" a time series
    s2_ds_1 = Sentinel2.from_safe(fpath_s2, vector_features=polys)
    assert s2_ds_1.is_scene, 'SceneProperties not set'
    s2_ds_2 = Sentinel2.from_safe(fpath_s2, vector_features=polys)
    assert s2_ds_2.is_scene, 'SceneProperties not set'
    # set the timing of the second scene to today
    s2_ds_2.scene_properties.acquisition_time = datetime.datetime.now()

    # open an empty SceneCollection
    scoll = SceneCollection()
    assert scoll.empty, 'SceneCollection must be empty'

    # open a SceneCollection by passing a constructor (RasterCollection + Timestamp)
    scoll = SceneCollection(
        scene_constructor=Sentinel2.from_safe,
        in_dir=fpath_s2,
        vector_features=polys
    )
    assert len(scoll) == 1, 'wrong number of scenes in collection'
    assert len(scoll.timestamps) == 1, 'wrong number of time stamps'
    assert len(scoll.timestamps) == len(scoll.identifiers), 'time stamps and identifers do not match'
    # try to get the scene by its timestamp
    rcoll = scoll[scoll.timestamps[0]]
    assert isinstance(rcoll, RasterCollection), 'expected a raster collection'
    assert not rcoll.empty, 'RasterCollection must not be empty'
    # try to get the scene by its identifier
    rcoll_id = scoll[scoll.identifiers[0]]
    assert isinstance(rcoll_id, RasterCollection), 'expected a raster collection'
    assert not rcoll_id.empty, 'RasterCollection must not be empty'
    assert rcoll.scene_properties.acquisition_time == rcoll_id.scene_properties.acquisition_time, \
        'selection by timestamp and identifier returned different results'

    # open a SceneCollection by passing a RasterCollection -> should raise an error
    # because the timestamp is missing
    fpath_no_scene = get_bandstack()
    with pytest.raises(ValueError):
        scoll = SceneCollection(
            scene_constructor=RasterCollection.from_multi_band_raster,
            fpath_raster=fpath_no_scene
        )

    # add another scene
    scoll.add_scene(s2_ds_2)
    assert len(scoll) == 2, 'wrong number of scenes'
    assert len(scoll.timestamps) == len(scoll.identifiers) == len(scoll), \
        'wrong number of items'
    assert scoll.timestamps[-1] == str(s2_ds_2.scene_properties.acquisition_time), 'wrong timestamp'
    assert scoll.timestamps[0] == str(s2_ds_1.scene_properties.acquisition_time), 'wrong timestamp'
    # add the same scene -> should raise an error
    with pytest.raises(KeyError):
        scoll.add_scene(s2_ds_2)

    # try working with slices
    # slice by date range
    scoll_daterange = scoll[date(2022,1,1):date(2999,12,31)]
    assert isinstance(scoll_daterange, SceneCollection), 'expected a SceneCollection'
    assert len(scoll_daterange) == 1, 'expected only a single scene in collection'
    # slice by date range, open end of slice
    scoll_daterange_openend = scoll[date(2022,1,1):]
    assert isinstance(scoll_daterange_openend, SceneCollection), 'expected a SceneCollection'
    assert len(scoll_daterange_openend) == 1, 'expected only a single scene in collection'
    # slice by date range, open start of slice
    scoll_daterange_openstart = scoll[:date(2022,1,1)]
    assert isinstance(scoll_daterange_openstart, SceneCollection), 'expected a SceneCollection'
    assert len(scoll_daterange_openstart) == 1, 'expected only a single scene in collection'
    # slice outside of daterange covered by SceneCollection
    assert scoll[date(1900,1,1):date(1901,12,31)].empty, 'SceneCollection returned must be empty'

    # test deleting a scene by its timestamp
    del(scoll[scoll.timestamps[0]])
    assert len(scoll) == 1, 'scene was not deleted'
    assert len(scoll.timestamps) == len(scoll.identifiers) == len(scoll), \
        'wrong number of items'

    # SceneCollection from list of scenes
    scenes_list = [s2_ds_1, s2_ds_2]
    scoll = SceneCollection.from_raster_collections(scenes_list)
    assert len(scoll) == 2, 'wrong number of scenes'
    assert scoll.is_sorted, 'expected a sorted SceneCollection'
    assert scoll.timestamps[0] == str(scenes_list[0].scene_properties.acquisition_time), \
        'wrong order of scenes'
    # from tuple
    scenes_tuple = tuple(scenes_list)
    scoll = SceneCollection.from_raster_collections(scenes_tuple)
    assert len(scoll) == 2, 'wrong number of scenes'
    assert scoll.is_sorted, 'expected a sorted SceneCollection'
    assert scoll.timestamps[0] == str(scenes_list[0].scene_properties.acquisition_time), \
        'wrong order of scenes'
    # descending order of scenes
    scoll = SceneCollection.from_raster_collections(scenes_tuple, sort_direction='desc')
    assert len(scoll) == 2, 'wrong number of scenes'
    assert scoll.is_sorted, 'expected a sorted SceneCollection'
    assert scoll.timestamps[-1] == str(scenes_list[0].scene_properties.acquisition_time), \
        'wrong order of scenes'
    # no sorting
    scoll = SceneCollection.from_raster_collections(scenes_tuple, sort_scenes=False)
    assert len(scoll) == 2, 'wrong number of scenes'
    assert not scoll.is_sorted, 'expected an unsorted SceneCollection'
    assert scoll.timestamps[0] == str(scenes_list[0].scene_properties.acquisition_time), \
        'wrong order of scenes'

    # sort the scene collection using its sort method
    s2_ds_3 = s2_ds_2.copy()
    test_time = datetime.datetime(1900,1,1)
    s2_ds_3.scene_properties.acquisition_time = test_time
    scoll = SceneCollection.from_raster_collections([s2_ds_1, s2_ds_2, s2_ds_3], sort_scenes=False)
    scoll_sorted = scoll.sort()
    assert scoll_sorted.is_sorted, 'expected a sorted SceneCollection'
    assert scoll_sorted.timestamps[0] == str(test_time), 'expected a different timestamp'
    # sort descending
    scoll_sorted_desc = scoll.sort(sort_direction='desc')
    assert scoll_sorted_desc.is_sorted, 'expected a sorted SceneCollection'
    assert scoll_sorted_desc.timestamps[-1] == str(test_time), 'expected a different timestamp'

def test_scene_collection_to_xarray(get_scene_collection):
    """convert SceneCollection to xarray"""
    scoll = get_scene_collection()
    xarr = scoll.to_xarray()
    assert isinstance(scoll[1000], RasterCollection), 'expected a RasterCollection'
    assert isinstance(xarr, xr.DataArray), 'expected a DataArray'
    assert len(xarr) == len(scoll), 'wrong length of DataArray'
    assert (xarr.time.values == scoll.timestamps).all(), 'wrong timestamps in DataArray'
    for idx in range(len(scoll)):
        assert (xarr.values[idx,:,:,:] == scoll[scoll.timestamps[idx]].get_values()).all(), 'wrong '

def test_scene_collection_time_series(get_scene_collection, generate_random_points, get_polygons):
    """time series extraction from scene collection"""
    scoll = get_scene_collection()
    # sample pixels randomly distributed within the scene collection's spatial extent
    bounds = scoll[1000]['B02'].bounds
    crs = scoll[1000]['B02'].crs
    # get 20 random points for which to extract the time series
    random_points = generate_random_points(20, bounds)
    random_points_gdf = gpd.GeoDataFrame(geometry=random_points, crs=crs)
    points_ts = scoll.get_feature_timeseries(vector_features=random_points_gdf)
    assert isinstance(points_ts, gpd.GeoDataFrame), 'expected a GeoDataFrame'
    assert 'acquisition_time' in points_ts.columns, 'missing time column'
    assert points_ts.shape == (60, 12), 'wrong shape of returned GeoDataFrame object'

    # test time series extraction using polygons and custom statistics
    methods = ['median', 'min']
    polys = get_polygons()
    # make sure there's an error raised when numpy nan functions are passed
    with pytest.raises(ValueError):
        scoll.get_feature_timeseries(vector_features=polys, method=['nanmedian'])
    polygons_ts = scoll.get_feature_timeseries(vector_features=polys, method=methods)
    assert isinstance(polygons_ts, gpd.GeoDataFrame), 'expected a GeoDataFrame'
    assert polygons_ts.iloc[1]['median'] == \
        scoll[1000]['B02'].reduce(by=polygons_ts.iloc[1].geometry, method='median')[0]['median'], \
            'values are not the same'

def test_dump_and_load(get_scene_collection, datadir):
    """dumping and loading SceneCollections to and from disk as pickled objects"""
    scoll = get_scene_collection()
    scoll_dumped = scoll.to_pickle()
    assert isinstance(scoll_dumped, bytes), 'expected a binary oject'
    scoll_reloaded = SceneCollection.from_pickle(scoll_dumped)
    assert scoll_reloaded.collection == scoll.collection, 'data in collection should be the same'
    assert scoll_reloaded.identifiers == scoll.identifiers, 'lost identifiers'

    # check saving to file and reading from it again
    fpath = datadir.joinpath('scene_collection.pkl')
    with open(fpath, 'wb') as f:
        f.write(scoll_dumped)

    scoll_reloaded_from_file = SceneCollection.from_pickle(fpath)
    assert scoll_reloaded_from_file.collection == scoll.collection, \
        'data in collection should be the same'

def test_plot_scene_collection(get_scene_collection):
    """plot scenes in collection"""
    scoll = get_scene_collection()
    # plot multiple bands
    f = scoll.plot(band_selection=['B02', 'B04', 'B05'])
    assert isinstance(f, plt.Figure), 'expected a matplotlib figure'
    # plot single band
    f = scoll.plot(band_selection=['B8A'], eodal_plot_kwargs={'colormap': 'viridis'})
    assert isinstance(f, plt.Figure), 'expected a matplotlib figure'

def test_clip_scene_collecton(get_scene_collection, get_polygons):
    """clip scene collection to field parcel boundaries"""
    scoll = get_scene_collection()
    field_parcel = gpd.read_file(get_polygons()).loc[[0]]
    scoll_clipped = scoll.clip_scenes(clipping_bounds=field_parcel, inplace=False)
    assert isinstance(scoll_clipped, SceneCollection), 'expected a SceneCollection'
    assert scoll_clipped[1000]['B02'].is_masked_array, 'expected a masked array'
    assert scoll_clipped[1000]['B02'].geo_info.ulx != scoll[1000]['B02'].geo_info.ulx, \
        'ulx must not be the same'
    assert scoll_clipped[1000]['B02'].geo_info.uly != scoll[1000]['B02'].geo_info.uly, \
        'uly must not be the same'
