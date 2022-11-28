'''
Created on Nov 24, 2022

@author: graflu
'''

import pytest
import datetime

from datetime import date

from eodal.core.band import Band
from eodal.core.raster import RasterCollection
from eodal.core.scene import SceneCollection
from eodal.core.sensors import Sentinel2

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
    