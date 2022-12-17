'''
Mapper class utility functions.

Copyright (C) 2022 Lukas Valentin Graf

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
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from typing import Dict, List, Optional

from eodal.core.raster import RasterCollection

def plot_feature(feature_scenes: List[RasterCollection], band_selection: str | List[str],
                 max_scenes_in_row: Optional[int] = 6,
                 eodal_plot_kwargs: Optional[Dict] = {},
                 feature_name: Optional[str] = '',
                 **kwargs) -> plt.Figure:
        """
        Plots all mapper retrieved for a feature

        :param band_selection:
            selection of band(s) to use for plotting. Must be either a single
            band or a set of three bands
        :returns:
            `Figure` object
        """
        # check number of passed bands
        if isinstance(band_selection, str):
            band_selection = [band_selection]
        if not len(band_selection) == 1 and not len(band_selection) == 3:
            raise ValueError('You must pass a single band name or three band names')

        plot_multiple_bands = True
        if len(band_selection) == 1:
            plot_multiple_bands = False

        # check number of mapper in feature_scenes and determine figure size
        n_scenes = len(feature_scenes)
        nrows = 1
        ncols = 1
        if n_scenes == 0:
            raise ValueError('No mapper available for plotting')
        elif n_scenes == 1:
            f, ax = plt.subplots(**kwargs)
            # cast to array to allow indexing
            ax = np.array([ax]).reshape(1,1)
        else:
            if n_scenes <= max_scenes_in_row:
                ncols = n_scenes
                f, ax = plt.subplots(ncols=ncols, nrows=nrows, **kwargs)
                # reshape to match the shape of ax array with >1 rows
                ax = ax.reshape(1, ax.size)
            else:
                nrows = int(np.ceil(n_scenes / max_scenes_in_row))
                ncols = max_scenes_in_row
                f, ax = plt.subplots(ncols=ncols, nrows=nrows, **kwargs)

        # get acquisition times of the mapper if available. If not label the
        # plots by ascending numbers (Scene 1, Scene 2, Scene 3,...)
        scene_labels = [
            f'{x.scene_properties.acquisition_time} {x.scene_properties.platform}' \
            if hasattr(x, 'scene_properties')  else f'Scene {idx+1}' for idx, x in \
            enumerate(feature_scenes)
        ]

        row_idx, col_idx = 0, 0
        for idx, feature_scene in enumerate(feature_scenes):
            if plot_multiple_bands:
                feature_scene.plot_multiple_bands(
                    band_selection=band_selection,
                    ax=ax[row_idx, col_idx],
                    **eodal_plot_kwargs
                )
            else:
                feature_scene[band_selection[0]].plot(
                    ax=ax[row_idx, col_idx],
                    **eodal_plot_kwargs
                )
            ax[row_idx, col_idx].set_title(scene_labels[idx])

            # switch off axes labels if sharex == True and sharey=True
            if kwargs.get('sharex', False) and kwargs.get('sharey', False) \
            and n_scenes > 1:
                if nrows > 1:
                    if row_idx < (nrows - 1): ax[row_idx, col_idx].set_xlabel('')
                if nrows > 1:
                    if col_idx > 0: ax[row_idx, col_idx].set_ylabel('')

            # increase column (and row) counter accordingly
            col_idx += 1
            # begin a new row when all columns are filled
            if col_idx == max_scenes_in_row:
                col_idx = 0
                row_idx += 1

        # make sure sub-plot labels do not overlap
        f.tight_layout()
        # figure title
        f.suptitle(feature_name)
        return f
