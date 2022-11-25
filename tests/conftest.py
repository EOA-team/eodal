'''
Global pytest fixtures
'''

import os
import pytest
import requests

from distutils import dir_util
from pathlib import Path
from eodal.downloader.utils import unzip_datasets

@pytest.fixture
def tmppath(tmpdir):
    '''
    Fixture to make sure that test function receive proper
    Posix or Windows path instead of 'localpath'
    '''
    return Path(tmpdir)

@pytest.fixture
def datadir(tmppath, request):
    '''
    Fixture responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely.

    Taken from stackoverflow
    https://stackoverflow.com/questions/29627341/pytest-where-to-store-expected-data
    (May 6th 2021)
    '''
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)

    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmppath))

    return tmppath

@pytest.fixture()
def get_project_root_path() -> Path:
    """
    returns the project root path
    """
    return Path(os.path.dirname(os.path.abspath(__file__))).parent

@pytest.fixture()
def get_s2_safe_l2a(get_project_root_path):
    """
    Get Sentinel-2 testing data in L2A processing level. If not available yet
    download the data from the Menedely dataset link provided (might take a while
    depending on your internet connection)
    """
    def _get_s2_safe_l2a():

        testdata_dir = get_project_root_path.joinpath('data')
        testdata_fname = testdata_dir.joinpath(
            'S2A_MSIL2A_20190524T101031_N0212_R022_T32UPU_20190524T130304.SAFE'
        )
    
        # download URL
        url = 'https://data.mendeley.com/public-files/datasets/ckcxh6jskz/files/e97b9543-b8d8-436e-b967-7e64fe7be62c/file_downloaded'
    
        if not testdata_fname.exists():
        
            # download dataset
            r = requests.get(url, stream=True)
            r.raise_for_status()
            testdata_fname_zip = str(testdata_fname).replace('.SAFE','.zip')
            with open(testdata_fname_zip, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=5096):
                    fd.write(chunk)
        
            # unzip dataset
            unzip_datasets(download_dir=testdata_dir, platform='S2')
            
        return testdata_fname

    return _get_s2_safe_l2a

@pytest.fixture()
def get_s2_safe_l1c(get_project_root_path):
    """
    Get Sentinel-2 testing data in L1C processing level. If not available yet
    download the data from the Menedely dataset link provided (might take a while
    depending on your internet connection)
    """
    def _get_s2_safe_l1c():

        testdata_dir = get_project_root_path.joinpath('data')
        testdata_fname = testdata_dir.joinpath(
            'S2B_MSIL1C_20190725T100039_N0208_R122_T33UWP_20190725T123957.SAFE'
        )
    
        # download URL
        url = 'https://data.mendeley.com/public-files/datasets/ckcxh6jskz/files/52abe583-c322-4ef1-8825-883fbfefe495/file_downloaded'
    
        if not testdata_fname.exists():
        
            # download dataset
            r = requests.get(url, stream=True)
            r.raise_for_status()
            testdata_fname_zip = str(testdata_fname).replace('.SAFE','.zip')
            with open(testdata_fname_zip, 'wb') as fd:
                for chunk in r.iter_content(chunk_size=5096):
                    fd.write(chunk)
        
            # unzip dataset
            unzip_datasets(download_dir=testdata_dir, platform='S2')
            
        return testdata_fname

    return _get_s2_safe_l1c

@pytest.fixture()
def get_bandstack(get_project_root_path):
    """
    Returns path to multi-band tiff file (bandstack)
    """

    def _get_bandstack():

        testdata_dir = get_project_root_path.joinpath('data')
        testdata_fname = testdata_dir.joinpath(
            '20190530_T32TMT_MSIL2A_S2A_pixel_division_10m.tiff'
        )
        return testdata_fname
    return _get_bandstack

@pytest.fixture()
def get_points(get_project_root_path):
    """
    Returns path to test points to be used for pixel extraction
    """
    
    def _get_points():
        
        testdata_dir = get_project_root_path.joinpath('data')
        testdata_points = testdata_dir.joinpath(
            Path('sample_points').joinpath('ZH_Points_2019_EPSG32632_random.shp')
        )
        return testdata_points
    return _get_points

@pytest.fixture()
def get_points2(get_project_root_path):
    """
    Returns path to test points to be used for pixel extraction
    """
    
    def _get_points():
        
        testdata_dir = get_project_root_path.joinpath('data')
        testdata_points = testdata_dir.joinpath(
            Path('sample_points').joinpath('sampling_test_points.shp')
        )
        return testdata_points
    return _get_points

@pytest.fixture()
def get_points3(get_project_root_path):
    """
    Returns path to test points to be used for pixel extraction
    """
    
    def _get_points():
        
        testdata_dir = get_project_root_path.joinpath('data')
        testdata_points = testdata_dir.joinpath(
            Path('sample_points').joinpath('BY_Points_2019_EPSG32633.shp')
        )
        return testdata_points
    return _get_points

@pytest.fixture()
def get_polygons(get_project_root_path):
    """
    Returns path to agricultural field polygons to use for masking
    """
    
    def _get_polygons():
        
        testdata_dir = get_project_root_path.joinpath('data')
        testdata_polys = testdata_dir.joinpath(
            Path('sample_polygons').joinpath('ZH_Polygons_2020_ESCH_EPSG32632.shp')
        )
        return testdata_polys
    return _get_polygons

@pytest.fixture()
def get_polygons_2(get_project_root_path):
    """
    Returns path to agricultural field polygons to use for masking
    """
    
    def _get_polygons():
        
        testdata_dir = get_project_root_path.joinpath('data')
        testdata_polys = testdata_dir.joinpath(
            Path('sample_polygons').joinpath('BY_AOI_2019_CLOUDS_EPSG32632.shp')
        )
        return testdata_polys
    return _get_polygons

@pytest.fixture()
def get_polygons_3(get_project_root_path):
    """
    Returns path to agricultural field polygons to use for masking
    """
    
    def _get_polygons():
        
        testdata_dir = get_project_root_path.joinpath('data')
        testdata_polys = testdata_dir.joinpath(
            Path('sample_polygons').joinpath('western_switzerland.gpkg')
        )
        return testdata_polys
    return _get_polygons
