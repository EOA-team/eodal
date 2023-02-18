'''
The Sentinel-2 mapper extension module to query, extract and pre-process Sentinel-2 data.

NOTE: This module was generated to provide users with an easy-to-use, low-key
approach to work with Sentinel-2 data. This means at the same time that the functions of
this module are rather static especially regarding the proposed preprocessing function
(_preprocess_scene). However, users can easily define their own preprocessing functions
using this module as a blueprint example.

Copyright (C) 2023 Lukas Valentin Graf

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from typing import Any, Callable, Dict, Optional

from eodal.core.raster import RasterCollection
from eodal.core.sensors import Sentinel2
from eodal.mapper.mapper import Mapper

def _preprocess_scene(
        ds: RasterCollection,
        resampling_kwargs: Optional[Dict[str,Any]] = {},
        mask_clouds: Optional[bool] = True,
        cloud_masking_kwargs: Optional[Dict[str,Any]] = {}
    ) -> RasterCollection:
    """
    Auxiliary function to spatially resample Sentinel-2 and optionally
    mask clouds and shadows.

    :param ds:
        Sentinel-2 Scene to process
    :param resampling_kwargs:
        optional keyword arguments to pass to `~ds.resample`. Leave empty (default)
        to omit spatial resampling.
    :param mask_clouds:
        optional boolean flag to specify if cloud masking based on the
        scene classification layer (SCL) should be carried out (True by default).
        IMPORTANT: Cloud masking works ONLY if Sentinel-2 bands were either
        resampled into a common spatial resolution or the 20m bands are used, only.
    :param cloud_masking_kwargs:
        optional keyword arguments to pass to `~ds.mask_clouds_and_shadows`. Leave
        empty to use default settings.
    :returns:
        pre-processed Sentinel-2 scene.
    """
    # check if resampling is requested
    if len(resampling_kwargs) == 0:
        resampled = ds
    else:
        # make sure the resampling method returns a RasterCollection object
        resampling_kwargs.update({'inplace': False})
        resampled = ds.resample(**resampling_kwargs)
    # optionally mask clouds and shadows
    if mask_clouds:
        # make sure the masking method returns a RasterCollection object
        cloud_masking_kwargs.update({'inplace': False})
        return ds.mask_cloud_and_shadows(**cloud_masking_kwargs)
    else:
        return resampled
        
class Sentinel2(Mapper):

    def __init__(
            self,
            **kwargs
        ):
        """Class constructor"""
        # call the super class constructor, setting the sensor to sentinel2
        kwargs.update({'sensor': 'sentinel2'})
        super().__init__(**kwargs)

    def load_scenes(
            self,
            scene_constructor_kwargs: Optional[Dict[str, Any]] = None,
            scene_modifier: Optional[Callable[RasterCollection,RasterCollection]] = _preprocess_scene,
            scene_modifier_kwargs: Optional[Dict[str,Any]] = {}
        ):
        """
        Overwrites the `load_scenes` method of the `Mapper` super-class.

        :param scene_constructor_kwargs:
            optional keyword-arguments to pass to `scene_constructor`. `fpath_raster`
            and `vector_features` are filled in by the `Mapper` instance automatically,
            i.e., any custom values passed will be overwritten.
        :param scene_modifier:
            optional Callable modifying a `RasterCollection` or returning a new
            `RasterCollection`. The Callable is applied to all scenes in the
            `SceneCollection` when loaded by the `Mapper`. Can be used, e.g.,
            to calculate spectral indices on the fly or for applying masks.
        :param scene_modifier_kwargs:
            optional keyword arguments for `scene_modifier` (if any).
        """
        # the scene_constructor is fixed to Sentinel-2, the other inputs are flexible
        scene_kwargs = {
            'scene_constructor': Sentinel2.from_safe,
            'scene_constructor_kwargs': scene_constructor_kwargs,
            'scene_modifier': scene_modifier,
            'scene_modifier_kwargs': scene_modifier_kwargs
        }
        # invoke method from super class
        super().load_scenes(scene_kwargs=scene_kwargs)
    