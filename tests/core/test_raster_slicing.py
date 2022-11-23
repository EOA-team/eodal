'''
Tests for slicing RasterCollections in a numpy style manner
'''

import pytest

from eodal.core.band import Band
from eodal.core.raster import RasterCollection

def test_raster_slice(get_bandstack):
    """test slicing of RasterCollections to get a subset"""

    fpath_raster = get_bandstack()
    color_names = ['blue', 'green', 'red', 'red_edge1', 'red_edge2', 'red_edge3', \
                   'nir1', 'nir2', 'swir1', 'swir2']
    ds = RasterCollection.from_multi_band_raster(
        fpath_raster=fpath_raster,
        band_aliases=color_names
    )

    # slicing using band names
    ds_sliced = ds['B02':'B04']
    assert len(ds_sliced) == 2, 'wrong number of bands returned from slice'
    assert ds_sliced.band_names == ['B02','B03'], 'wrong bands returned from slice'

    ds_sliced = ds['B03':'B8A']
    assert len(ds_sliced) == 6, 'wrong number of bands returned from slice'
    assert ds_sliced.band_names == ['B03', 'B04', 'B05', 'B06', 'B07', 'B08'], \
        'wrong bands returned from slice'

    # slicing using aliases
    ds_sliced_aliases = ds['blue':'red']
    assert len(ds_sliced_aliases) == 2, 'wrong number of bands returned from slice'
    assert ds_sliced_aliases.band_names == ['B02','B03'], 'wrong bands returned from slice'

    # slicing using same start and stop -> should return an empty collection
    assert ds['B04':'B04'].empty, 'expected an empty RasterCollection'

    # slicing using reverse order -> should return an empty collection
    assert ds['B08':'B03'].empty, 'expected an empty RasterCollection'

    # slices with open bounds
    slice_open_end = ds['B02':]
    assert len(slice_open_end) == 10, 'wrong number of bands returned'
    assert slice_open_end.band_names == ds.band_names, 'messed up band names'

    slice_open_start = ds[:'B05']
    assert len(slice_open_start) == 3, 'wrong number of bands returned'
    assert slice_open_start.band_names == ['B02', 'B03', 'B04'], 'messed up band names'

    slice_with_stride = ds['B03':'B8A':2]
    assert len(slice_with_stride) == 3, 'wrong number of bands returned'
    assert slice_with_stride.band_names == ['B03', 'B05', 'B07'], 'messed up band names'

    single_band = ds['B04']
    assert isinstance(single_band, Band), 'expected a band object'

    single_band = ds['red']
    assert isinstance(single_band, Band), 'expected a band object'
    