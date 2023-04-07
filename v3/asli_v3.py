import os
import xarray as xr
import numpy as np
import pandas as pd
from datetime import datetime
from skimage.feature import peak_local_max

### seasonal or monthly mean?
seasonal_averaging = False
testing = False

### era5, era-interim
indata = 'era5'

### Update this as the ASL / low detection algorithm is updated
### version_id = 3.<DATE>
version_id = '3.20210820-'+indata # +'-TESTING' 

def asl_sector_mean(da, asl_region, mask):
    a = da.where(mask == 0).sel( latitude=slice(asl_region['north'],asl_region['south']), 
                longitude=slice(asl_region['west'],asl_region['east']) ).mean().values
    return a

# def apply_gaussian_filter(da, sigma=11)
#     import scipy.ndimage as ndimage
#     img = ndimage.gaussian_filter(da.values, sigma=sigma)
#     da.values = img
#     return da


def season_mean(ds, calendar="standard"):
    # # Make a DataArray with the number of days in each month, size = len(time)
    # month_length = ds.time.dt.days_in_month

    # # Calculate the weights by grouping by 'time.season'
    # weights = (
    #     month_length.groupby("time.season") / month_length.groupby("time.season").sum()
    # )

    # # Test that the sum of the weights for each season is 1.0
    # np.testing.assert_allclose(weights.groupby("time.season").sum().values, np.ones(4))

    # # Calculate the weighted average
    # return (ds * weights).groupby("time.season").sum(dim="time")

    return ds.resample(time='QS-Mar').mean('time')

def get_lows(da, mask):
    '''
    da for one point in time (with lats x lons)
    '''
    
    lons, lats = da.longitude.values, da.latitude.values
    
    sector_mean_pres = asl_sector_mean(da, asl_region, mask)
    threshold = sector_mean_pres

    if 'season' in da.coords: 
        time_str = str(da_t.season.values)
    else:
        time_str = str(da.time.values)[:10]

    # fill land in with highest value to limit lows being found here
    da_max   = da.max().values
    da       = da.where(mask == 0).fillna(da_max)
        
    invert_data = (da*-1.).values     # search for peaks rather than minima
    
    if threshold is None:
        threshold_abs = invert_data.mean()
    else:
        threshold_abs  = threshold * -1  # define threshold cut-off for peaks (inverted lows)
                
    ### these seem suitable for ERA5 data + resolution
    minima_yx = peak_local_max(invert_data,             # input data
                           min_distance=5,              # peaks are separated by at least min_distance
                           num_peaks=3,                 # maximum number of peaks
                           exclude_border=False,        # excludes peaks from within min_distance - pixels of the border
                           threshold_abs=threshold_abs  # minimum intensity of peaks
                           )
    
    minima_lat, minima_lon, pressure = [], [], []
    for minima in minima_yx:
        minima_lat.append(lats[minima[0]])
        minima_lon.append(lons[minima[1]])
        pressure.append(da.values[minima[0],minima[1]])
    
    df = pd.DataFrame()
    df['lat']        = minima_lat
    df['lon']        = minima_lon
    df['ActCenPres'] = pressure
    df['SectorPres'] = sector_mean_pres
    df['time']       = time_str
    
    ### Add relative central pressure (Hosking et al. 2013)
    df['RelCenPres'] = df['ActCenPres'] - df['SectorPres']

    ### re-order columns
    df = df[['time','lon','lat','ActCenPres','SectorPres','RelCenPres']]
    
    ### clean-up DataFrame
    df = df.reset_index(drop=True)

    return df

def define_asl(df, region):
    ### select only those points within ASL box
    df2 = df[(df['lon'] > region['west'])  & 
                (df['lon'] < region['east'])  & 
                (df['lat'] > region['south']) & 
                (df['lat'] < region['north']) ]

    ### For each time, get the row with the lowest minima_number
    df2 = df2.loc[df2.groupby('time')['ActCenPres'].idxmin()]
    
    df2 = df2.reset_index(drop=True)

    return df2

def slice_region(da, region, boarder=8):
    da = da.sel( latitude=slice(region['north']+boarder,region['south']-boarder), 
                longitude=slice(region['west']-boarder,region['east']+boarder))
    return da

def write_csv_with_header(df, header, version_id, indata, time_averaging):

    if testing:
        if '-TESTING' not in version_id:
            version_id = version_id+'-TESTING'

    if header == 'asli':     
        fname = indata+'/asli_'+time_averaging+'_v'+version_id+'-197901-202212.csv'
    if header == 'all_lows': 
        fname = indata+'/all_lows_'+time_averaging+'_v'+version_id+'-197901-202212.csv'

    with open('csv_header_asli_v3.txt') as header_file:  
        lines = header_file.readlines()

    with open(fname, 'w') as file:
        for line in lines:
            if (header == 'all_lows'):
                line = line.replace('Amundsen Sea Low (ASL) Index version 3',
                                    'Detected lows within the Pacific sector of the Southern Ocean')
            line = line.replace( '<SOURCE_DATA>', indata.upper() )
            line = line.replace('ASLi_version_id = 3.XXXX', 'ASLi_version_id = '+version_id)
            line = line.replace('END-OF-FILE','\n')
            file.write('# '+str(line))

        df.to_csv(file, index=False)

# Analysis
print(indata)

root = '/glade/work/zespinosa/data/index/ASL/amundsen-sea-low-index/data'
da   = xr.open_dataset(os.path.join(root, 'era5_mean_sea_level_pressure_monthly_197901-202212.nc')).msl

root_mask = '/glade/work/zespinosa/GRIDS'
mask = xr.open_dataset(os.path.join(root_mask, 'era5_land_sea_mask_25x25.nc')).lsm.squeeze()
# Rename dim
mask = mask.rename({'lat':'latitude', 'lon':'longitude'})
# Drop coords
mask = mask.reset_coords(names=["realization", "time", "experimentVersionNumber"], drop=True)
# Reset Longitudes
mask["longitude"] = np.concatenate([da["longitude"][720:].values, da["longitude"][:720].values])

if seasonal_averaging == True:
    da = season_mean(da, calendar="standard")

da_mask = da.where(mask == 0)

# region of interest (asl sector)
asl_region = {'west':170., 'east':298., 'south':-80., 'north':-60.}

### slice area around ASL region
da      = slice_region(da, asl_region)
da_mask = slice_region(da_mask, asl_region)

# change units
da = da / 100. 
da = da.assign_attrs(units='hPa')

if 'season' in da.dims: 
    ntime = 4
if 'time' in da.dims: 
    ntime = da.time.shape[0]

all_lows_dfs = pd.DataFrame()

for t in range(0,ntime):
    if 'season' in da.dims: da_t = da.isel(season=t)
    if 'time' in da.dims:   da_t = da.isel(time=t)

    all_lows_df  = get_lows(da_t, mask)
    all_lows_dfs = pd.concat([all_lows_dfs, all_lows_df], ignore_index=True)

asl_df = define_asl(all_lows_dfs, asl_region)

### Write CSV files
if seasonal_averaging == False:
    write_csv_with_header( asl_df,       'asli',     version_id, indata, 'monthly' )
    write_csv_with_header( all_lows_dfs, 'all_lows', version_id, indata, 'monthly' )

### TO DO: detect whether asl_df is seasonal within the def and adjust fname accordingly
if seasonal_averaging == True:
    write_csv_with_header( asl_df,       'asli',     version_id, indata, 'seasonal' )
    write_csv_with_header( all_lows_dfs, 'all_lows', version_id, indata, 'seasonal' )