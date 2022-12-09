'''
Created on Nov 20, 2022

@author: graflu
'''

import numpy as np
import pytest

from copy import deepcopy
from typing import List, Optional

from eodal.core.band import Band
from eodal.core.raster import RasterCollection

def sqrt_per_band(
    raster_collection: RasterCollection,
    band_selection: Optional[List[str]] = None
) -> RasterCollection:
    """
    Calculate the square root per band in RasterCollection.

    :param raster_collection:
        non-empty raster collection
    :param band_selection:
        optional list of bands for which to calculate the square root
    :returns:
        RasterCollection object with square root values
    """
    # make sure the RasterCollection is not empty
    if raster_collection.empty:
        raise ValueError('Passed RasterCollection must not be empty')

    # check passed bands
    _band_selection = deepcopy(band_selection)
    if _band_selection is None:
        _band_selection = raster_collection.band_names

    # calculate the square root per band
    out_collection = RasterCollection()
    for band_name in _band_selection:
        vals = raster_collection[band_name].values
        if isinstance(vals, np.ma.MaskedArray):
            sqrt_vals = np.ma.sqrt(vals)
        else:
            sqrt_vals = np.sqrt(vals)
        out_collection.add_band(
            Band,
            values=sqrt_vals,
            geo_info=raster_collection[band_name].geo_info,
            band_name=f'SQRT({raster_collection[band_name].band_name})',
        )
    out_collection.scene_properties = raster_collection.scene_properties
    return out_collection

def test_apply_custom_function(get_bandstack):
    """
    test applying a custom function to a RasterCollection
    """
    fpath_raster = get_bandstack()
    gTiff_collection = RasterCollection.from_multi_band_raster(
        fpath_raster=fpath_raster
    )

    # define a custom function for calculation the square root of values
    # per band
    out_collection_func = sqrt_per_band(raster_collection=gTiff_collection)
    # apply the function to the RasterCollection
    out_collection_apply = gTiff_collection.apply(sqrt_per_band)
    assert isinstance(out_collection_apply, RasterCollection), \
        'apply did not return a RasterCollection'

    assert (out_collection_func['SQRT(B02)'] ==  out_collection_apply['SQRT(B02)']).values.all(), \
        'RasterCollection.apply and applying the function to RasterCollection did yield different results'

    assert (gTiff_collection['B02'] ==  out_collection_apply['SQRT(B02)']).values.any(), \
        'RasterCollection.apply had no effect'

    # apply to selection of bands
    out_collection = gTiff_collection.apply(sqrt_per_band, band_selection=['B03'])
    assert len(out_collection.band_names) == 1, 'wrong number of bands'

    # apply to masked RasterCollection
    mask = gTiff_collection['B02'] < 1000
    masked_collection = gTiff_collection.mask(mask=mask)
    out_collection_masked = masked_collection.apply(sqrt_per_band)
    assert not out_collection_masked.empty, 'Output is empty'
    assert out_collection_masked['SQRT(B02)'].is_masked_array, \
        'returned band is not masked'

    # incorrect apply calls
    with pytest.raises(TypeError):
        # function missing
        gTiff_collection.apply(band_selection=['B02'])

    with pytest.raises(ValueError):
        # wrong argument passed to function
        gTiff_collection.apply(sqrt_per_band, dummy='false-arg')
    