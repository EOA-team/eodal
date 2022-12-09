"""
Sample script showing how to load a cloud-optimized GeoTiff
into a `Band` object

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
"""

from eodal.core.band import Band

# link to cloud-optimized geoTiffs at Swisstopp
dem_file = 'https://data.geo.admin.ch/ch.swisstopo.swissalti3d/swissalti3d_2019_2618-1092/swissalti3d_2019_2618-1092_2_2056_5728.tif'

# load resource into a Band instance and name it "Elevation"
dem = Band.from_rasterio(fpath_raster=dem_file, band_name_dst='Elevation')
print(dem)
# will display:
# EOdal Band
# ---------.
# Name:    Elevation
# GeoInfo:    {'epsg': 2056, 'ulx': 2618000.0, 'uly': 1093000.0, 'pixres_x': 2.0, 'pixres_y': -2.0}

# fast visualization
fig = dem.plot(
    colormap='terrain',
    colorbar_label=f'Elevation above Mean Sea Level [m]'
)

fig.savefig('../img/eodal_SwissALTI3D_sample.png', dpi=150, bbox_inches='tight')
