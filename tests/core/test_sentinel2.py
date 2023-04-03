
import cv2
import pytest
import requests
import numpy as np

from rasterio.coords import BoundingBox
from pathlib import Path
from shapely.geometry import Polygon
from matplotlib.figure import Figure
from datetime import date

from eodal.config import get_settings
from eodal.core.sensors import Sentinel2
from eodal.core.band import Band
from eodal.utils.exceptions import BandNotFoundError, InputError

settings = get_settings()
settings.USE_STAC = False

def test_read_pixels_from_safe(get_s2_safe_l1c, get_s2_safe_l2a, get_points2, get_points3):
    """
    Tests reading pixels from a .SAFE archive using class and instance methods
    """
    # test pixels
    test_point_features = get_points2()

    # test L1C data with pixel lying complete outside of the scene extent
    safe_archive = get_s2_safe_l1c()

    # use class method (no reading of spectral bands required)
    gdf_classmethod = Sentinel2.read_pixels_from_safe(
        vector_features=test_point_features,
        in_dir=safe_archive
    )
    assert gdf_classmethod.empty, \
        'pixel values returned although sample points lay completely outside of scene extent' 

    # do the same using the instance method instead
    handler = Sentinel2().from_safe(
        in_dir=safe_archive,
        band_selection=['B02']
    )

    gdf_instancemethod = handler.get_pixels(vector_features=test_point_features)
    assert gdf_instancemethod.empty, 'pixel values returned although sample points lay completely outside of scene extent' 

    # read points from L1C partly inside the scene extent without scaling
    test_point_features = get_points3()

    gdf_classmethod = Sentinel2().read_pixels_from_safe(
        vector_features=test_point_features,
        in_dir=safe_archive,
        apply_scaling=False
    )

    assert gdf_classmethod.shape[0] == 4, 'wrong number of pixels extracted'

    s2_bands = ['B02','B03','B04','B05','B06','B07','B08','B8A','B11','B12']
    gdf_attributes = [x for x in s2_bands if x in gdf_classmethod.columns]
    assert s2_bands == gdf_attributes, 'not all bands extracted'
    assert 'SCL' not in gdf_classmethod.columns, 'SCL is not available for L1C data'

    assert set(gdf_classmethod.B02) == set([875, 795, 908, 749]), 'wrong values for band 02'
    assert set(gdf_classmethod.B11) == set([1756, 2532, 990, 1254]), 'wrong values for band 11'

    # apply scaling
    gdf_classmethod = Sentinel2().read_pixels_from_safe(
        vector_features=test_point_features,
        in_dir=safe_archive,
        apply_scaling=True
    )
    assert (0 < gdf_classmethod.B02).all() and (gdf_classmethod.B02 < 1).all(), 'wrong values for band 02'
    assert (0 < gdf_classmethod.B11).all() and (gdf_classmethod.B11 < 1).all(), 'wrong values for band 11'

    # do the same with the instance method (read bands and then extract the pixels from
    # the read bands)
    handler = Sentinel2().from_safe(
        in_dir=safe_archive,
        band_selection=['B02','B11','B12']
    )

    # make sure band selection works with band and color names
    gdf_instancemethod_colornames = handler.get_pixels(
        vector_features=test_point_features,
        band_selection=['blue','swir_1']
    )
    assert 'B02' in gdf_instancemethod_colornames.columns and \
        'B11' in gdf_instancemethod_colornames.columns, 'color names not recognized'

    gdf_instancemethod_bandnames = handler.get_pixels(
        vector_features=test_point_features,
        band_selection=['B02','B11']
    )
    assert 'B02' in gdf_instancemethod_bandnames.columns and \
        'B11' in gdf_instancemethod_bandnames.columns, 'band names not recognized'

    assert (
        gdf_instancemethod_bandnames[['B02','B11']].values == gdf_instancemethod_colornames[['B02','B11']].values
    ).all(), 'selecting bands by band and color names returned different results'

    assert gdf_instancemethod_colornames.shape[0] == 4, 'wrong number of pixels extracted'

    # test L2A data
    test_point_features = get_points2()
    safe_archive = get_s2_safe_l2a()

    gdf_classmethod = Sentinel2().read_pixels_from_safe(
        vector_features=test_point_features,
        in_dir=safe_archive
    )
    assert gdf_classmethod.empty, 'pixel values returned although all of the are outside of the scene extent'
    assert 'SCL' in gdf_classmethod.columns, 'SCL not attempted to extract'

def test_read_from_safe_l1c(get_s2_safe_l1c):
    """handling of Sentinel-2 data in L1C processing level from .SAFE archives"""
    in_dir = get_s2_safe_l1c()

    # read without AOI file
    band_selection = ['B04', 'B05', 'B8A']
    reader = Sentinel2().from_safe(
        in_dir=in_dir,
        band_selection=band_selection
    )
    # check if the object can be considered a band stack -> should not be the case
    assert not reader.is_bandstack(), 'data is labeled as band-stack but it should not'
    assert reader['red'].wavelength_info.central_wavelength == 664.9, \
        'central wavelength not set properly for red band'
    assert reader['nir_2'].wavelength_info.central_wavelength == 864.0, \
        'central wavelength not set properly for nir_2 band'

    # check scene properties
    acquisition_time = reader.scene_properties.acquisition_time
    assert acquisition_time.date() == date(2019,7,25), 'acquisition date is wrong'
    assert reader.scene_properties.sensor == 'MSI', 'wrong sensor'
    assert reader.scene_properties.platform == 'S2B', 'wrong platform'
    assert reader.scene_properties.processing_level.value == 'LEVEL1C', 'wrong processing level'

    # check band list
    bands = reader.band_names
    assert len(bands) == len(band_selection), 'number of bands is wrong'
    assert 'SCL' not in bands, 'SCL band cannot be available for L1C data'

def test_read_from_safe_with_mask_l2a(datadir, get_s2_safe_l2a, get_polygons, get_polygons_2):
    """handling Sentinel-2 data from .SAFE archives (masking)"""
    in_dir = get_s2_safe_l2a()
    in_file_aoi = get_polygons()

    # read using polygons outside of the tile extent -> should fail
    with pytest.raises(Exception):
        handler = Sentinel2().from_safe(
            in_dir=in_dir,
            vector_features=in_file_aoi
        )

    # read using polygons overlapping the tile extent
    in_file_aoi = get_polygons_2()

    handler = Sentinel2.from_safe(
        in_dir=in_dir,
        vector_features=in_file_aoi
    )
    assert not handler.is_bandstack(), 'data read from SAFE archive cannot be a bandstack'

    # after resampling of all bands to 10m data should be bandstacked
    resampled = handler.resample(target_resolution=10.)
    assert resampled.is_bandstack(), 'after resampling bands must be bandstacked'
    assert (resampled['green'].values == handler['green'].values).all(), \
        'values of bands in target resolution must not change'
    assert abs(resampled['nir_2'].values.mean() - handler['nir_2'].values.mean()) < 1e-5, \
        'nearest neighbor resampling should not change band statistics'

    # make sure meta information was saved correctly
    assert handler['scl'].meta['dtype'] == 'uint8', 'wrong data type for SCL in meta'

    # to_xarray should fail because of different spatial resolutions
    with pytest.raises(ValueError):
        handler.to_xarray()

    # as well as the calculation of the TCARI-OSAVI ratio
    with pytest.raises(NotImplementedError):
        handler.calc_si('TCARI_OSAVI', inplace=True)

    # but calculation of NDVI should work because it requires the 10m bands only
    handler.calc_si('NDVI', inplace=True)
    assert 'NDVI' in handler.band_names, 'NDVI not added to handler'

    ndvi = handler.calc_si('NDVI', inplace=False)
    assert isinstance(ndvi, np.ma.MaskedArray), 'wrong return type'
    assert 0 < ndvi.mean() < 1, 'NDVI cannot get bigger than 1'
    assert (handler['NDVI'].values == ndvi).all(), \
        'index calculation did not produce the same results'

    # stacking bands should fail because of different spatial resolutions
    with pytest.raises(ValueError):
        handler.get_values()

    # dropping all 20m should then allow stacking operations and conversion to xarray
    bands_to_drop = ['B05', 'B06', 'B07', 'B8A', 'B11', 'B12', 'SCL']
    for band_to_drop in bands_to_drop:
        handler.drop_band(band_to_drop)

    assert len(handler.band_names) == 5, 'too many bands left'
    assert len(handler.band_aliases) == len(handler.band_names), \
        'band aliases were not deleted during drop operation'
    assert set(handler.band_aliases) == {'blue', 'green', 'red', 'nir_1', 'ndvi'}, \
        'wrong band aliases left'
    assert handler.is_bandstack(), 'data should now fulfill bandstack criteria'

    xds = handler.to_xarray()

    # make sure attributes were set correctly in xarray
    assert len(xds.attrs['scales']) == len(handler.band_names), 'wrong number of bands in attributes'
    assert xds.attrs['descriptions'] == tuple(handler.band_aliases), \
        'band description not set properly'

def test_ignore_scl(datadir, get_s2_safe_l2a, get_polygons_2):
    """ignore the SCL on reading"""
    in_dir = get_s2_safe_l2a()
    in_file_aoi = get_polygons_2()

    # read using polygons outside of the tile extent -> should fail
    handler = Sentinel2.from_safe(
        in_dir=in_dir,
        vector_features=in_file_aoi,
        read_scl=False
    )
    assert 'SCL' not in handler.band_names, 'SCL band should not be available'

    # read with weird band ordering
    band_selection = ['B07','B06']
    handler = Sentinel2().from_safe(
        in_dir=in_dir,
        vector_features=in_file_aoi,
        band_selection=band_selection,
        read_scl=False
    )
    assert 'SCL' not in handler.band_names, 'SCL band should not be available'
    # make sure the bands are always order ascending no matter how the input order was
    assert handler.band_names == ['B06', 'B07'], 'wrong order of bands'
    assert handler.band_aliases == ['red_edge_2', 'red_edge_3'], 'wrong order of band aliases'
    with pytest.raises(KeyError):
        handler['SCL'].meta

def test_band_selections(datadir, get_s2_safe_l2a, get_polygons, get_polygons_2,
                         get_bandstack):
    """testing invalid band selections"""

    in_dir = get_s2_safe_l2a()
    in_file_aoi = get_polygons_2()

    # attempt to read no-existing bands
    handler = Sentinel2()
    with pytest.raises(BandNotFoundError):
        handler.from_safe(
            in_dir=in_dir,
            vector_features=in_file_aoi,
            band_selection=['B02','B13']
        )

def test_read_from_safe_l2a(datadir, get_s2_safe_l2a):
    """handling Sentinel-2 data from .SAFE archives (no masking)"""
    in_dir = get_s2_safe_l2a()

    # read without AOI file
    band_selection = ['B02', 'B03', 'B04', 'B08', 'B8A']
    reader = Sentinel2().from_safe(
        in_dir=in_dir,
        band_selection=band_selection
    )

    # check if the object can be considered a band stack -> should not be the case
    assert not reader.is_bandstack(), 'data is labelled as band-stack but it should not'

    # check scene properties
    acquisition_time = reader.scene_properties.acquisition_time
    assert acquisition_time.date() == date(2019,5,24), 'acquisition date is wrong'
    assert reader.scene_properties.sensor == 'MSI', 'wrong sensor'
    assert reader.scene_properties.platform == 'S2A', 'wrong platform'
    assert reader.scene_properties.processing_level.value == 'LEVEL2A', 'wrong processing level'

    # check band list
    bands = reader.band_names
    assert len(bands) == len(band_selection), 'number of bands is wrong'
    assert 'SCL' in bands, 'expected SCL band'

    # check band aliases
    aliases = reader.band_aliases
    assert len(aliases) == len(bands), 'number of aliases does not match number of bands'

    # check single band data
    blue = reader.get_band('B02').copy()

    assert type(blue.values) in (np.ndarray, np.array), 'wrong datatype for band'
    assert len(blue.values.shape) == 2, 'band array is not 2-dimensional'
    assert (blue.nrows, blue.ncols) == (10980, 10980), 'wrong shape of band array'
    assert blue.values.min() >= 0., 'reflectance data must not be smaller than zero'

    scl = reader.get_band('scl')
    assert type(scl.values) in (np.ndarray, np.array), 'wrong datatype for band'
    assert scl.values.dtype == 'uint8', 'SCL has dtype uint8'
    assert (scl.nrows, scl.ncols) == (5490,5490), 'wrong shape of band array'
    assert scl.values.max() < 12, 'invalid value for scl'
    assert scl.values.min() >= 0, 'invalid value for scl'

    assert reader['blue'].geo_info.pixres_x == 10, 'blue should have a spatial resolution of 10m'
    assert reader['blue'].geo_info.pixres_x == -reader['blue'].geo_info.pixres_y, \
        'signs of x and y should be different'
    assert reader['scl'].geo_info.pixres_x == 20, \
        'scl should have a spatial resolution of 20m before resampling'
    assert reader['nir_2'].geo_info.pixres_x == 20, \
        'B8A should have a spatial resolution of 20m before resampling'

    # get non-exisiting bands
    with pytest.raises(BandNotFoundError):
        non_existing_band = reader.get_band('B01')

    # check the RGB
    fig_rgb = reader.plot_multiple_bands(band_selection=['red','green','blue'])
    assert type(fig_rgb) == Figure, 'plotting of RGB bands failed'

    # check the scene classification layer
    fig_scl = reader.plot_scl()
    assert type(fig_scl) == Figure, 'plotting of SCL failed'

    spectral_bands = reader.band_names
    spectral_bands.remove('SCL')
    reader.resample(
        target_resolution=10,
        interpolation_method=cv2.INTER_CUBIC,
        band_selection=spectral_bands,
        inplace=True
    )

    # SCL should not have changed
    assert reader.get_values(['scl']).shape == (1, 5490,5490), 'SCL was resampled although excluded'

    # but B8A should have 10m resolution now
    assert reader.get_values(['B8A']).shape == (1,10980,10980), 'B8A was not resampled although selected'
    assert reader['B8A'].geo_info.pixres_x == 10, 'geo info was not updated'

    # add custom band
    band_to_add = np.zeros_like(blue.values)
    reader.add_band(
        band_constructor=Band,
        band_name='test',
        values=band_to_add,
        geo_info=reader['blue'].geo_info
    )
    assert (reader['test'].values == band_to_add).all(), 'band was not added correctly'
    assert 'test' in reader.band_names, 'band "test" not found in reader entries'

    # check cloud masking using SCL
    cloudy_pixels = reader.get_cloudy_pixel_percentage()
    assert 0 <= cloudy_pixels <= 100, 'cloud pixel percentage must be between 0 and 100%'

    # check blackfill (there is some but not the entire scene is blackfilled)
    assert not reader.is_blackfilled, 'blackfill detection did not work out - to many false positives'

    # blackfill_mask = reader.get_blackfill('blue')
    # assert blackfill_mask.dtype == bool, 'A boolean mask is required for the blackfill'
    # assert 0 < np.count_nonzero(blackfill_mask) < np.count_nonzero(~blackfill_mask)

    # try masking using the SCL classes. Since SCL is not resampled yet this should fail
    with pytest.raises(Exception):
        reader.mask_clouds_and_shadows(bands_to_mask=['blue'])

    # resample SCL and try masking again
    reader.resample(target_resolution=10, inplace=True)

    reader.mask_clouds_and_shadows(bands_to_mask=['blue'], inplace=True)
    reader.mask_clouds_and_shadows(bands_to_mask=['B03', 'B04'], inplace=True)

    # drop a band
    reader.drop_band('test')

    assert 'test' not in reader.band_names, 'band "test" still available although dropped'
    with pytest.raises(BandNotFoundError):
        reader.get_band('test')
    with pytest.raises(KeyError):
        reader['test'].meta

    # re-project a band to another UTM zone (33)
    reader.reproject(
        target_crs=32633,
        blackfill_value=0,
        inplace=True
    )

    assert reader.is_bandstack(), 'data should fulfill bandstack criteria but doesnot'
    assert reader['blue'].crs == 32633, 'projection was not updated'

    # try writing bands to output file
    reader.to_rasterio(
        fpath_raster=datadir.joinpath('scl.tif'),
        band_selection=['scl']
    )

    assert datadir.joinpath('scl.tif').exists(), 'output raster file not found'

    # try converting data to xarray
    xds = reader.to_xarray()

    assert xds.crs == 32633, 'EPSG got lost in xarray dataset'
