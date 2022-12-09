|GHA tests| |Codecov report| |pre-commit| |black|

""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
E:earth_africa:dal Earth Observation Data Analysis Library
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

................................................................................
A truely open-source package for unified analysis of Earth Observation (EO) data
................................................................................

.. contents:: Overview
   :depth: 3

========================
About E:earth_africa:dal
========================

E:earth_africa:dal is a Python library enabling the acquisition, organization, and analysis of Earth observation data in a completely open-source manner.

E:earth_africa:dal Python allows to

	* load
	* modify
	* analyze
	* write
	* and interface

EO data within an unified framework. E:earth_africa:dal thus enables open-source, reproducible geo-spatial data science while lowering the burden of data handling on the user-side.
E:earth_africa:dal supports working in **cloud-environments** using [STAC catalogs](https://stacspec.org/) ("online" mode) and
on **local premises** using a spatial PostgreSQL/PostGIS database to organize metadata ("offline" mode).

Read more about E:earth_africa:dal in [this peer reviewed article](https://doi.org/10.1016/j.compag.2022.107487).

========================
Citing E:earth_africa:dal
========================

When using EOdal not only refer to our [license agreement](LICENSE) but also cite us properly:

.. code::latex

	@article{GRAF2022107487,
	title = {EOdal: An open-source Python package for large-scale agroecological research using Earth Observation and gridded environmental data},
	journal = {Computers and Electronics in Agriculture},
	volume = {203},
	pages = {107487},
	year = {2022},
	issn = {0168-1699},
	doi = {https://doi.org/10.1016/j.compag.2022.107487},
	url = {https://www.sciencedirect.com/science/article/pii/S0168169922007955},
	author = {Lukas Valentin Graf and Gregor Perich and Helge Aasen},
	keywords = {Satellite data, Python, Open-source, Earth Observation, Ecophysiology},
	abstract = {Earth Observation by means of remote sensing imagery and gridded environmental data opens tremendous opportunities for systematic capture, quantification and interpretation of plant–environment interactions through space and time. The acquisition, maintenance and processing of these data sources, however, requires a unified software framework for efficient and scalable integrated spatio-temporal analysis taking away the burden of data and file handling from the user. Existing software products either cover only parts of these requirements, exhibit a high degree of complexity, or are closed-source, which limits reproducibility of research. With the open-source Python library EOdal (Earth Observation Data Analysis Library) we propose a novel software that enables the development of fully reproducible spatial data science chains through the strict use of open-source developments. Thanks to its modular design, EOdal enables advanced data warehousing especially for remote sensing data, sophisticated spatio-temporal analysis and intersection of different data sources, as well as nearly unlimited expandability through application programming interfaces (APIs).}
	}

==============================
Examples of E:earth_africa:dal
==============================

The following code snippet reads spectral bands from a Sentinel-2 scene
organized in .SAFE folder structure acquired over Southern Germany in
Level2A (bottom-of-atmosphere reflectance). The Sentinel-2 scene can be
downloaded `here <https://data.mendeley.com/datasets/ckcxh6jskz/1>`__ (
S2A_MSIL2A_20190524T101031_N0212_R022_T32UPU_20190524T130304.zip):

.. code:: python

   import geopandas as gpd
   from pathlib import Path
   from shapely.geometry import Polygon
   from eodal.core.sensors import Sentinel2

   # file-path to the .SAFE dataset
   dot_safe_dir = Path('../data/S2A_MSIL2A_20190524T101031_N0212_R022_T32UPU_20190524T130304.SAFE')

   # construct a bounding box for reading a spatial subset of the scene (geographic coordinates)
   ymin, ymax = 47.949, 48.027
   xmin, xmax = 11.295, 11.385
   bbox = Polygon([(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)])

   # eodal expects a vector file or a GeoDataFrame for spatial sub-setting
   bbox_gdf = gpd.GeoDataFrame(geometry=[bbox], crs=4326)

   # read data from .SAFE (all 10 and 20m bands + scene classification layer)
   s2_ds = Sentinel2().from_safe(
       in_dir=dot_safe_dir,
       vector_features=bbox_gdf
   )

   # eodal support band aliasing. Thus, you can access the bands by their name ...
   s2_ds.band_names

Output

.. code:: shell

   >>> ['B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B11', 'B12', 'SCL']

.. code:: python

   # ... or by their alias, i.e., their color name
   s2_ds.band_aliases

.. code:: shell

   >>> ['blue', 'green', 'red', 'red_edge_1', 'red_edge_2', 'red_edge_3', 'nir_1', 'nir_2', 'swir_1', 'swir_2', 'scl']

.. code:: python

   # plot false-color infrared preview
   s2_ds.plot_multiple_bands(band_selection=['nir_1','red','green'])

.. image:: img/eodal_Sentinel-2_NIR.png
  :width: 400
  :alt: Sentinel-2 False-Color NIR

.. code:: python

   # plot scene classification layer
   s2_ds.plot_scl()

.. image:: img/eodal_Sentinel-2_SCL.png
  :width: 400
  :alt: Sentinel-2 Scene classification layer


============
Contributing
============

Contributions to E:earth_africa:dal are welcome. Please make sure to read the [contribution guidelines](Contributing.rst) first.
