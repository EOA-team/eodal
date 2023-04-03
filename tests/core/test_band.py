"""
Tests for `~eodal.core.Band`
"""

import cv2
import geopandas as gpd
import numpy as np
import pytest
import rasterio as rio
import zarr

from shapely.geometry import Polygon

from eodal.core.band import Band
from eodal.core.band import GeoInfo

def test_base_constructors():
    """
    test base constructor calls
    """
    epsg = 32633
    ulx = 300000
    uly = 5100000
    pixres_x, pixres_y = 10, -10
    
    geo_info = GeoInfo(
        epsg=epsg,
        ulx=ulx,
        uly=uly,
        pixres_x=pixres_x,
        pixres_y=pixres_y
    )
    assert isinstance(geo_info.as_affine(), rio.Affine), 'wrong Affine type'

    # invalid EPSG code
    epsg = 0
    with pytest.raises(ValueError):
        geo_info = GeoInfo(
        epsg=epsg,
        ulx=ulx,
        uly=uly,
        pixres_x=pixres_x,
        pixres_y=pixres_y
    )

    band_name = 'test'
    values = np.zeros(shape=(2,4))

    band = Band(band_name=band_name, values=values, geo_info=geo_info)
    assert type(band.bounds) == Polygon, 'band bounds must be a Polygon'
    assert not band.has_alias, 'when color name is not set, the band has no alias'
    assert band.band_name == band_name, 'wrong name for band'

    assert band.values[0,0] == 0., 'wrong value for band data'

    assert band.meta['height'] == band.nrows, 'wrong raster height in meta'
    assert band.meta['width'] == band.ncols, 'wrong raster width in meta'
    assert band.is_ndarray, 'must be of type ndarray'
    assert band.crs.is_epsg_code, 'EPSG code not valid' 

    zarr_values = zarr.zeros((10,10), chunks=(5,5), dtype='float32')
    band = Band(band_name=band_name, values=zarr_values, geo_info=geo_info)
    assert band.is_zarr

def test_band_from_rasterio(get_test_band, get_bandstack):
    """
    Tests instance and class methods of the `Band` class
    """
    band = get_test_band()
    
    assert band.geo_info.epsg == 32632, 'wrong EPSG code'
    assert band.band_name == 'B02', 'wrong band name'
    assert band.is_masked_array, 'array has not been masked'
    assert band.alias is None, 'band alias was not set'
    assert set(band.coordinates.keys()) == {'x', 'y'}, 'coordinates not set correctly'
    assert band.nrows == band.values.shape[0], 'number of rows does not match data array'
    assert band.ncols == band.values.shape[1], 'number of rows does not match data array'
    assert band.coordinates['x'].shape[0] == band.ncols, \
        'number of x coordinates does not match number of columns'
    assert band.coordinates['y'].shape[0] == band.nrows, \
        'number of y coordinates does not match number of rows'
    assert band.values.min() == 19, 'wrong minimum returned from data array'
    assert band.values.max() == 9504, 'wrong maximum returned from data array'
    assert band.geo_info.ulx == 475420.0, 'wrong upper left x coordinate'
    assert band.geo_info.uly == 5256840.0, 'wrong upper left y coordinate'

    band_bounds_mask = band.bounds
    assert band_bounds_mask.type == 'Polygon'
    assert band_bounds_mask.exterior.bounds[0] == band.geo_info.ulx, \
        'upper left x coordinate does not match'
    assert band_bounds_mask.exterior.bounds[3] == band.geo_info.uly, \
        'upper left y coordinate does not match'

    assert not band.values.mask.all(), 'not all pixels should be masked'

    fig = band.plot(colorbar_label='Surface Reflectance')
    assert fig is not None, 'no figure returned'

    # try some cases that must fail
    # reading from non-existing file
    with pytest.raises(rio.errors.RasterioIOError):
        Band.from_rasterio(
            fpath_raster='not_existing_file.tif'
        )
    # existing file but reading wrong band index
    fpath_raster = get_bandstack()
    with pytest.raises(IndexError):
        Band.from_rasterio(
            fpath_raster=fpath_raster,
            band_idx=22,
        )

def test_reprojection(datadir, get_test_band):
    """reprojection into another CRS"""
    # define test data sources
    
    band = get_test_band()
    # reproject to Swiss Coordinate System (EPSG:2056)
    reprojected = band.reproject(target_crs=2056)

    assert reprojected.crs == 2056, 'wrong EPSG after reprojection'
    assert reprojected.is_masked_array, 'mask must not be lost after reprojection'
    assert np.round(reprojected.geo_info.ulx) == 2693130.0, 'wrong upper left x coordinate'
    assert np.round(reprojected.geo_info.uly) == 1257861.0, 'wrong upper left y coordinate'
    fpath_out = datadir.joinpath('reprojected.jp2')
    reprojected.to_rasterio(fpath_out)
    with rio.open(fpath_out, 'r') as src:
        meta = src.meta
    # make sure everything was saved correctly to file
    assert meta['crs'] == reprojected.crs
    assert meta['height'] == reprojected.nrows
    assert meta['width'] == reprojected.ncols
    assert meta['transform'] == reprojected.transform

def test_bandstatistics(get_test_band):

    band = get_test_band()
    # get band statistics
    stats = band.reduce(method=['mean', 'min', 'max'])
    mean_stats = band.reduce(method='mean')
    assert mean_stats[0]['mean'] == stats[0]['mean'], 'miss-match of metrics'
    assert stats[0]['min'] == band.values.min(), 'minimum not calculated correctly'
    assert stats[0]['max'] == band.values.max(), 'maximum not calculated correctly'

    # convert to GeoDataFrame
    gdf = band.to_dataframe()
    assert (gdf.geometry.type == 'Point').all(), 'wrong geometry type'
    assert set(gdf.columns) == {'geometry', 'B02'}, 'wrong column labels'
    assert gdf.shape[0] == 29674, 'wrong number of pixels converted'
    assert gdf.B02.max() == stats[0]['max'], 'band statistics not the same after conversion'
    assert gdf.B02.min() == stats[0]['min'], 'band statistics not the same after conversion'
    assert gdf.B02.mean() == stats[0]['mean'], 'band statistics not the same after conversion'

def test_to_xarray(get_test_band):
    band = get_test_band()
    # convert to xarray
    xarr = band.to_xarray()
    assert xarr.x.values[0] == band.geo_info.ulx + 0.5*band.geo_info.pixres_x, \
        'pixel coordinate not shifted to center of pixel in xarray'
    assert xarr.y.values[0] == band.geo_info.uly + 0.5*band.geo_info.pixres_y, \
        'pixel coordinate not shifted to center of pixel in xarray'
    assert (xarr.values == band.values.astype(float)).all(), \
        'array values changed after conversion to xarray'
    assert np.count_nonzero(~np.isnan(xarr.values)) == band.values.compressed().shape[0], \
        'masked values were not set to nan correctly'
    assert xarr.shape[1] == band.nrows and xarr.shape[2] == band.ncols, \
        'wrong number of rows and columns in xarray'

def test_resampling(get_test_band):
    band = get_test_band()
    # resample to 20m spatial resolution using bi-cubic interpolation
    resampled = band.resample(
        target_resolution=20,
        interpolation_method=cv2.INTER_CUBIC
    )
    assert resampled.geo_info.pixres_x == 20, 'wrong pixel size after resampling'
    assert resampled.geo_info.pixres_y == -20, 'wrong pixel size after resampling'
    assert resampled.geo_info != band.geo_info, 'geo info must not be the same'
    assert resampled.ncols < band.ncols, 'spatial resolution should decrease'
    assert resampled.nrows < band.ncols, 'spatial resolution should decrease'
    assert resampled.is_masked_array, 'mask should be preserved'

    # resample to 5m inplace
    old_shape = (band.nrows, band.ncols)
    band.resample(
        target_resolution=5,
        inplace=True
    )
    assert band.nrows == 588, 'wrong number of rows after resampling'
    assert band.ncols == 442, 'wrong number of columns after resampling'
    assert band.is_masked_array, 'mask should be preserved'

    # resample back to 10m and align to old shape
    band.resample(
        target_resolution=10,
        target_shape=old_shape,
        interpolation_method=cv2.INTER_CUBIC,
        inplace=True
    )

    assert (band.nrows, band.ncols) == old_shape, 'resampling to target shape did not work'

def test_masking(datadir, get_test_band, get_bandstack, get_points3):
    """masking of band data"""
    band = get_test_band()
    mask = np.ndarray(band.values.shape, dtype='bool')
    mask.fill(True)

    # try without inplace
    masked_band = band.mask(mask=mask, inplace=False)
    assert isinstance(masked_band, Band), 'wrong return type'
    assert (masked_band.values.mask == mask).all(), 'mask not applied correctly'
    assert (masked_band.values.data == band.values.data).all(), 'data not preserved correctly'

    band.mask(mask=mask, inplace=True)
    assert band.values.mask.all(), 'not all pixels masked'

    # test scaling -> nothing should happen at this stage
    values_before_scaling = band.values
    band.scale_data()
    assert (values_before_scaling.data == band.values.data).all(), 'scaling must not have an effect'

    # read data with AOI outside of the raster bounds -> should raise a ValueError
    fpath_raster = get_bandstack()
    vector_features_2 = get_points3()
    with pytest.raises(ValueError):
        band = Band.from_rasterio(
            fpath_raster=fpath_raster,
            band_idx=1,
            band_name_dst='B02',
            vector_features=vector_features_2,
            full_bounding_box_only=False
        )

    # write band data to disk
    fpath_out = datadir.joinpath('test.jp2')
    band.to_rasterio(fpath_raster=fpath_out)

    assert fpath_out.exists(), 'output dataset not written'
    band_read_again = Band.from_rasterio(fpath_out)
    assert (band_read_again.values == band.values.data).all(), \
        'band data not the same after writing'

def test_read_pixels(get_bandstack, get_test_band, get_polygons, get_points3):
    # read single pixels from raster dataset
    fpath_raster = get_bandstack()
    vector_features = get_polygons()

    pixels = Band.read_pixels(
        fpath_raster=fpath_raster,
        vector_features=vector_features
    )
    assert 'B1' in pixels.columns, 'extracted band data not found'
    gdf = gpd.read_file(vector_features)
    assert pixels.shape[0] == gdf.shape[0], 'not all geometries extracted'
    assert pixels.geometry.type.unique().shape[0] == 1, 'there are too many different geometry types'
    assert pixels.geometry.type.unique()[0] == 'Point', 'wrong geometry type'

    # compare against results from instance method
    band = get_test_band()
    pixels_inst = band.get_pixels(vector_features)
    assert (pixels.geometry == pixels_inst.geometry).all(), \
        'pixel geometry must be always the same'
    assert band.band_name in pixels_inst.columns, 'extracted band data not found'

    # try features outside of the extent of the raster
    vector_features_2 = get_points3()
    pixels = Band.read_pixels(
        fpath_raster=fpath_raster,
        vector_features=vector_features_2
    )
    assert (pixels.B1 == 0).all(), 'nodata not set properly to features outside of raster extent'

    # read with full bounding box (no masking just spatial sub-setting)
    band = Band.from_rasterio(
        fpath_raster=fpath_raster,
        band_idx=1,
        band_name_dst='B02',
        vector_features=vector_features,
        full_bounding_box_only=True
    )

    assert not band.is_masked_array, 'data should not be masked'
    assert band.is_ndarray, 'band data should be ndarray'

    mask = np.ndarray(band.values.shape, dtype='bool')
    mask.fill(True)
    mask[100:120,100:200] = False
    band.mask(mask=mask, inplace=True)
    assert band.is_masked_array, 'band must now be a masked array'
    assert not band.values.mask.all(), 'not all pixel should be masked'
    assert band.values.mask.any(), 'some pixels should be masked'

    resampled = band.resample(target_resolution=5)
    assert band.geo_info.pixres_x == 10, 'resolution of original band should not change'
    assert band.geo_info.pixres_y == -10, 'resolution of original band should not change'
    assert resampled.geo_info.pixres_x == 5, 'wrong x pixel resolution'
    assert resampled.geo_info.pixres_y == -5, 'wrong y pixel resolution'
    assert resampled.bounds == band.bounds, 'band bounds should be the same after resampling'

def test_from_vector(get_polygons):
    vector_features = get_polygons()

    # read data from vector source
    epsg = 32632
    gdf = gpd.read_file(vector_features)
    ulx = gdf.geometry.total_bounds[0]
    uly = gdf.geometry.total_bounds[-1]
    pixres_x, pixres_y = 10, -10
    
    geo_info = GeoInfo(
        epsg=epsg,
        ulx=ulx,
        uly=uly,
        pixres_x=pixres_x,
        pixres_y=pixres_y
    )
    band = Band.from_vector(
        vector_features=vector_features,
        geo_info=geo_info,
        band_name_src='GIS_ID',
        band_name_dst='gis_id',
    )
    bounds = band.bounds

    assert band.band_name == 'gis_id', 'wrong band name inserted'
    assert band.values.dtype == 'float32', 'wrong data type for values'
    assert band.geo_info.pixres_x == 10, 'wrong pixel size in x direction'
    assert band.geo_info.pixres_y == -10, 'wrong pixel size in y direction'
    assert band.geo_info.ulx == ulx, 'wrong ulx coordinate'
    assert band.geo_info.uly == uly, 'wrong uly coordinate'
    assert band.geo_info.epsg == 32632, 'wrong EPSG code'

    # with custom datatype
    band = Band.from_vector(
        vector_features=vector_features,
        geo_info=geo_info,
        band_name_src='GIS_ID',
        band_name_dst='gis_id',
        dtype_src='uint16',
        snap_bounds=bounds
    )
    assert band.values.dtype == 'uint16', 'wrong data type'

    # test with point features
    point_gdf = gpd.read_file(vector_features)
    point_gdf.geometry = point_gdf.geometry.apply(lambda x: x.centroid)

    band_from_points = Band.from_vector(
        vector_features=point_gdf,
        geo_info=geo_info,
        band_name_src='GIS_ID',
        band_name_dst='gis_id',
        dtype_src='uint32'
    )
    assert band_from_points.values.dtype == 'uint32', 'wrong data type'
    assert band_from_points.reduce(method='max')[0]['max'] == \
        point_gdf.GIS_ID.values.astype(int).max(), 'miss-match in band statistics'

def test_clip_band(get_test_band):
    """
    test clipping a band by a rectangle (spatial sub-setting)
    """
    band = get_test_band()
    # define a polygon to clip the band to
    # first case: the polygon is smaller than the band and lies within its bounds
    band_bounds = band.bounds
    clip_bounds = band_bounds.buffer(-20)
    band_clipped = band.clip(clipping_bounds=clip_bounds)
    assert isinstance(band_clipped, Band), 'expected a band object'
    assert band_clipped.band_name == band.band_name, 'band name not copied'
    assert band_clipped.alias == band.alias, 'band alias not copied'
    assert band_clipped.unit == band.unit, 'unit not copied'
    assert band_clipped.scale == band.scale, 'scale not copied'
    assert band_clipped.offset == band.offset, 'offset not copied'
    assert band_clipped.transform != band.transform, 'the transformation must not be the same'
    assert band_clipped.nrows < band.nrows, 'number of rows of clipped band must be smaller'
    assert band_clipped.ncols < band.ncols, 'number of columns of clipped band must be smaller'
    expected_shape = (
        int(band.nrows - 4), #  -4 because of 20m inwards buffering (resolution is 10m)
        int(band.ncols - 4) #  -4 because of 20m inwards buffering (resolution is 10m)
    )
    assert band_clipped.values.shape == expected_shape, 'wrong shape of clipped band'

    # second case: clip to a polygon larger than the Band -> should return the same Band
    clip_bounds = band.bounds.buffer(20)
    band_clipped = band.clip(clip_bounds)
    assert (band_clipped == band).values.all(), 'the bands must be the same'

    # third case: bounding box outside the Band -> should raise an error
    clip_bounds = (100, 100, 300, 300)
    with pytest.raises(ValueError):
        band_clipped = band.clip(clip_bounds)

    # fourth case: bounding box is the same as the bounds of the Band
    clip_bounds = band.bounds
    band_clipped = band.clip(clip_bounds)
    assert (band_clipped == band).values.all(), 'the bands must be the same'

    # fifth case: bounding box partially overlaps the Band (different test cases)
    band_bounds_xy = clip_bounds.exterior.xy
    clip_bounds = (
        min(band_bounds_xy[0]) - 100, # xmin
        min(band_bounds_xy[1]) - 231, # ymin
        max(band_bounds_xy[0]) - 44,  # xmax
        max(band_bounds_xy[1]) - 85   # ymax
    )
    band_clipped = band.clip(clip_bounds)
    assert band_clipped.nrows < band.nrows, 'number of rows must not be the same'
    assert band_clipped.ncols < band.ncols, 'number of columns must not be the same'
    # all rows should be the same but not the columns
    clip_bounds = (
        min(band_bounds_xy[0]) - 1000, # xmin
        min(band_bounds_xy[1]), # ymin
        max(band_bounds_xy[0]) - 1000,  # xmax
        max(band_bounds_xy[1])   # ymax
    )
    band_clipped = band.clip(clip_bounds)
    assert band_clipped.nrows == band.nrows, 'number of rows must be the same'
    assert band_clipped.ncols < band.ncols, 'number of columns must not be the same'
    assert band_clipped.geo_info.ulx == band.geo_info.ulx, 'upper left x should be the same'
    assert band_clipped.geo_info.uly == band.geo_info.uly, 'upper left y should be the same'
    # all columns should be the same but not the rows
    clip_bounds = (
        min(band_bounds_xy[0]), # xmin
        min(band_bounds_xy[1]) - 2000, # ymin
        max(band_bounds_xy[0]),  # xmax
        max(band_bounds_xy[1]) - 2000  # ymax
    )
    band_clipped = band.clip(clip_bounds)
    assert band_clipped.nrows < band.nrows, 'number of rows must not be the same'
    assert band_clipped.ncols == band.ncols, 'number of columns must be the same'
    assert band_clipped.geo_info.ulx == band.geo_info.ulx, 'upper left x should be the same'
    assert band_clipped.geo_info.uly == band.geo_info.uly - 2000, 'wrong upper left y coordinate'

    # test with inplace == True
    band_before_clip = band.copy()
    band.clip(clip_bounds, inplace=True)
    assert band_clipped.nrows < band_before_clip.nrows, 'number of rows must not be the same'
    assert band_clipped.ncols == band_before_clip.ncols, 'number of columns must be the same'
    assert band_clipped.geo_info.ulx == band_before_clip.geo_info.ulx, 'upper left x should be the same'
    assert band_clipped.geo_info.uly == band_before_clip.geo_info.uly - 2000, 'wrong upper left y coordinate'

def test_clip_band_small_extents(get_project_root_path):
    # geometry for clipping data to
    small_test_geom = Polygon(
        [[493504.953633058525156, 5258840.576098721474409],
        [493511.206339373020455, 5258839.601945200935006],
        [493510.605988947849255, 5258835.524093257263303],
        [493504.296645800874103, 5258836.554883609525859],
        [493504.953633058525156, 5258840.576098721474409]]
    )
    gdf = gpd.GeoDataFrame(geometry=[small_test_geom], crs=32632)
    # raster data to clip
    testdata_dir = get_project_root_path.joinpath('data')
    fpath_raster = testdata_dir.joinpath('T32TMT_20220728T102559_B02_10m.tif')
    # get band
    band = Band.from_rasterio(
        fpath_raster=fpath_raster,
        band_idx=1,
        band_name_dst='B02',
        nodata=0
    )
    clipped = band.clip(clipping_bounds=gdf, full_bounding_box_only=True)
    assert clipped.values.shape == (2,2), 'wrong shape'
    assert (clipped.values == np.array([[1716, 1698],[1690, 1690]])).all(), \
        'wrong values returned'
    assert not clipped.is_masked_array, 'should not be a masked array'

def test_reduce_band_by_polygons(get_polygons, get_test_band):
    """reduction of band raster values by polygons"""
    # test reduction by external features
    polys = get_polygons()
    band = get_test_band()
    method = ['mean', 'median', 'max']
    poly_stats = band.reduce(method=method, by=polys)
    # comment out this test because in v0.2.0 empty results are discarded by default
    # assert len(poly_stats) == gpd.read_file(polys).shape[0], 'wrong number of polygons returned'
    assert set(method).issubset(poly_stats[0].keys()), 'expected different naming of results'
    assert 'geometry' in poly_stats[0].keys(), 'geometry attribute was lost'

    # reduce by a limited number of polygons
    polys_reduced = gpd.read_file(polys).iloc[0:10]
    poly_stats_reduced = band.reduce(method=method, by=polys_reduced)
    assert len(poly_stats_reduced) == polys_reduced.shape[0], 'wrong number of polygons returned'
    assert poly_stats_reduced == poly_stats[0:10], 'wrong order of results'

    # reduce by passing the "self" keyword (features must be set)
    poly_stats_self = band.reduce(method=method, by='self')
    # comment out this test because in v0.2.0 empty results are discarded by default
    # assert len(poly_stats_self) == band.vector_features.shape[0], 'wrong number of polygons'
    assert poly_stats_self == poly_stats, 'both approaches should return exactly the same'

    # call reduce without passing "by" -> should return a single result
    all_stats = band.reduce(method=method)
    assert len(all_stats) == 1, 'there must not be more than a single result'
