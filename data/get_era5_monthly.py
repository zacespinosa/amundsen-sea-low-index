import numpy as np

import cdsapi

variables = [
    # '10m_u_component_of_wind',
    # '10m_v_component_of_wind',
    # '2m_temperature',
    'mean_sea_level_pressure']

startYr, endYr = 1979, 2023
yrs = [str(yr) for yr in np.arange(startYr, endYr)]

for variable in variables:

    print(variable)

    c = cdsapi.Client()
    c.retrieve(
        'reanalysis-era5-single-levels-monthly-means',
        {
            'product_type':'monthly_averaged_reanalysis',
            'variable':variable,
            'year': yrs,
            'month':[
                '01','02','03',
                '04','05','06',
                '07','08','09',
                '10','11','12'
            ],
            'time':'00:00',
            'format':'netcdf'
        },
        f'era5_{variable}_monthly_{startYr}01-{int(endYr-1)}12.nc')
