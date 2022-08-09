'''
Created on Aug 9, 2022

@author: graflu
'''

# TODO
if __name__ == '__main__':

    from eodal.metadata.stac import sentinel1 as s1_stac_client
    from eodal.core.sensors import Sentine1 
    import matplotlib.pyplot as plt
    from datetime import date
    from pathlib import Path

    # define time period
    date_start = date(2022, 5, 1)
    date_end = date(2022, 5, 31)

    # provide bounding box
    bounding_box_fpath = Path(
        # '/home/graflu/public/Evaluation/Projects/KP0031_lgraf_PhenomEn/02_Field-Campaigns/Strickhof/WW_2022/Bramenwies.shp'
        '/mnt/ides/Lukas/software/eodal/data/sample_polygons/ZH_Polygon_73129_ESCH_EPSG32632.shp'
    )

    # Sentinel-1
    res_s1 = s1_stac_client(
        date_start=date_start,
        date_end=date_end,
        vector_features=bounding_box_fpath,
        collection='sentinel-1-rtc'
    )
    res_s1 = res_s1.sort_values(by='datetime')


    f, ax = plt.subplots(nrows=1, ncols=res_s1.shape[0], figsize=(20,5), sharex=True)

    # loop datasets and plot CR
    for idx, rec in res_s1.iterrows():
        asset = rec['assets']
    
        s1 = Sentinel1.from_safe(in_dir=asset, vector_features=bounding_box_fpath)
        s1.calc_si('CR', inplace=True)

        s1.plot_band('CR', ax=ax[idx], colorbar_label='CR [-]', vmin=0, vmax=4)
        if idx > 0:
            ax[idx].set_ylabel('')
        ax[idx].set_title(f'{s1.scene_properties.acquisition_time}\n{s1.scene_properties.platform}')

    f.tight_layout()
    f.savefig('/mnt/ides/Lukas/software/eodal/img/sentinel1_cr.png', bbox_inches='tight')
    plt.close(f)
            