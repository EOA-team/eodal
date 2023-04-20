
from datetime import datetime
from eodal.config import get_settings
from eodal.core.sensors import Sentinel1
from eodal.mapper.feature import Feature
from eodal.mapper.filter import Filter
from eodal.mapper.mapper import Mapper, MapperConfigs
from shapely.geometry import Polygon

Settings = get_settings()

if __name__ == '__main__':

    collection = 'sentinel1-grd'
    time_start = datetime(2020,7,1)
    time_end = datetime(2020,7,15)
    geom = Polygon(
        [[493504.953633058525156, 5258840.576098721474409],
        [493511.206339373020455, 5258839.601945200935006],
        [493510.605988947849255, 5258835.524093257263303],
        [493504.296645800874103, 5258836.554883609525859],
        [493504.953633058525156, 5258840.576098721474409]]
    )
    metadata_filters = [Filter('product_type','==', 'GRD')]

    Settings.USE_STAC = True

    feature = Feature(
        name='Test Area',
        geometry=geom,
        epsg=32632,
        attributes={'id': 1}
    )
    mapper_configs = MapperConfigs(
        collection=collection,
        time_start=time_start,
        time_end=time_end,
        feature=feature,
        metadata_filters=metadata_filters
    )
    mapper = Mapper(mapper_configs)
    mapper.query_scenes()

    mapper.metadata

    scene_kwargs = {
	    'scene_constructor': Sentinel1.from_safe,
	    'scene_constructor_kwargs': {'epsg_code': 4326}
	}
    mapper.load_scenes(scene_kwargs=scene_kwargs)

    import rasterio as rio
    import planetary_computer
    fpath = mapper.metadata.real_path.iloc[0]['vh']['href']
    ds = rio.open(planetary_computer.sign_url(fpath))

    ds_l = rio.open('/mnt/ides/Lukas/Download/iw-vh.tiff')