import numpy as np

import logging
logger = logging.getLogger(__name__)


def distance(ϕ1, λ1, ϕ2, λ2):
    from constants import R

    # Calculate the distance between two points on the Earth (ϕ1, λ1) and (ϕ1, λ1) using the haversine formula.
    # See: http://www.movable-type.co.uk/scripts/latlong.html
    # Latitudes are denoted by ϕ while longitudes are denoted by λ.

    ϕ1, λ1, ϕ2, λ2 = np.deg2rad([ϕ1, λ1, ϕ2, λ2])
    Δϕ = ϕ2 - ϕ1
    Δλ = λ2 - λ1

    a = np.sin(Δϕ/2)**2 + np.cos(ϕ1) * np.cos(ϕ2) * np.sin(Δλ/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R*c


def log_netCDF_dataset_metadata(dataset):
    # Nicely format dimension names and sizes.
    dim_string = ""
    for dim in dataset.dimensions:
        dim_name = dataset.dimensions[dim].name
        dim_size = dataset.dimensions[dim].size
        dim_string = dim_string + dim_name + '(' + str(dim_size) + ') '

    # Nicely format variable information.
    var_string = ""
    for var in dataset.variables:
        var_type = dataset.variables[var].dtype
        var_name = dataset.variables[var].name

        var_dim_str = '('
        for dim in dataset.variables[var].dimensions:
            var_dim_str = var_dim_str + str(dim) + ', '
        var_dim_str = var_dim_str[:-2] + ')'

        var_string = var_string + str(var_type) + ' ' + var_name + var_dim_str + ', '

    logger.info('Title: {:s}'.format(dataset.title))
    logger.info('Data model: {:s}'.format(dataset.data_model))
    logger.info('Dimensions: {:s}'.format(dim_string))
    logger.info('Variables: {:s}'.format(var_string[:-2]))


def latlon_to_polar_stereographic_xy(lat, lon):
    # This function converts from geodetic latitude and longitude to polar stereographic (x,y) coordinates for the polar
    # regions. The original equations are from Snyder, J. P., 1982,  Map Projections Used by the U.S. Geological Survey,
    # Geological Survey Bulletin 1532, U.S. Government Printing Office.  See JPL Technical Memorandum 3349-85-101 for
    # further details.
    #
    # The original FORTRAN program written by C. S. Morris, April 1985, Jet Propulsion Laboratory, California
    # Institute of Technology
    #
    # More information:
    # http://nsidc.org/data/polar-stereo/ps_grids.html
    # http://nsidc.org/data/polar-stereo/tools_geo_pixel.html
    # https://nsidc.org/data/docs/daac/nsidc0001_ssmi_tbs/ff.html
    #
    # SSM/I: Special Sensor Microwave Imager
    # Note: lat must be positive for the southern hemisphere! Or take absolute value like below.

    sgn = -1  # Sign of the latitude (use +1 for northern hemisphere, -1 for southern)
    e = 0.081816153  # Eccentricity of the Hughes ellipsoid
    R_E = 6378.273e3  # Radius of the Hughes ellipsode [m]
    slat = 70  # Standard latitude for the SSM/I grids is 70 degrees.

    # delta is the meridian offset for the SSM/I grids (0 degrees for the South Polar grids; 45 degrees for the
    # North Polar grids).
    delta = 45 if sgn == 1 else 0

    lat, lon = np.deg2rad([abs(lat), lon+delta])

    t = np.tan(np.pi/4 - lat/2) / ((1 - e*np.sin(lat)) / (1 + e*np.sin(lat)))**(e/2)

    if np.abs(90 - lat) < 1e-5:
        rho = 2*R_E*t / np.sqrt((1+e)**(1+e) * (1-e)**(1-e))
    else:
        sl = slat * np.pi/180
        t_c = np.tan(np.pi/4 - sl/2) / ((1 - e*np.sin(sl)) / (1 + e*np.sin(sl)))**(e/2)
        m_c = np.cos(sl) / np.sqrt(1 - e*e * (np.sin(sl)**2))
        rho = R_E * m_c * (t/t_c)
        logger.debug('rho = {:f}, m_c = {:f}, t = {:f}, t_c = {:f}'.format(rho, m_c, t, t_c))

    x = rho * sgn * np.sin(sgn * lon)
    y = -rho * sgn * np.cos(sgn * lon)

    return x, y


def convert_lon_range_to_0360(old_lon_min, old_lon_max):
    # TODO: Properly convert lat = -180:180 to lat = 0:360. List comprehension then sort?
    if old_lon_min == -180 and old_lon_max == 180:
        return 0, 360


def interpolate_dataset(data, lats, lons, pickle_filepath, mask_value_cond, interp_method='cubic',
                        repeat0tile1=True, convert_lon_range=False, polar_stereographic_grid=False):
    import pickle
    from os.path import isfile

    # Check if the data has already been interpolated for the same grid points before doing the interpolation again. If
    # so, load the file, unpickle it and return the interpolated grid.
    if isfile(pickle_filepath):
        logger.info('Interpolated grid already computed and saved. Unpickling: {:s}'.format(pickle_filepath))
        with open(pickle_filepath, 'rb') as f:
            data_interp_dict = pickle.load(f)
            data_interp = data_interp_dict['data_interp']
            latgrid_interp = data_interp_dict['latgrid_interp']
            longrid_interp = data_interp_dict['longrid_interp']
        return data_interp, latgrid_interp, longrid_interp

    from scipy.interpolate import griddata
    from constants import lat_min, lat_max, n_lat, lon_min, lon_max, n_lon

    logger.info('Options: convert_lon_range_to_0360={}, polar_stereographic_grid={}'.format(convert_lon_range,
                                                                                            polar_stereographic_grid))
    logger.info('Data information:')
    logger.info('lats.min={}, lats.max={}, lats.shape={}'.format(lats.min(), lats.max(), lats.shape))
    logger.info('lons.min={}, lons.max={}, lons.shape={}'.format(lons.min(), lons.max(), lons.shape))
    logger.info('data.min={}, data.max={}, data.shape={}'.format(data.min(), data.max(), data.shape))

    logger.info('Interpolation grid information:')
    logger.info('lat_min={}, lat_max={}, n_lat={}'.format(lat_min, lat_max, n_lat))
    logger.info('lon_min={}, lon_max={}, n_lon={}'.format(lon_min, lon_max, n_lon))

    # Mask certain values (e.g. land, missing data) according to the mask value condition and reshape into a 1D array
    # in preparation for griddata.
    data_masked = np.ma.array(data, mask=mask_value_cond(data))

    logger.info('Plotting masked data.')
    import matplotlib.pyplot as plt
    if repeat0tile1:
        plt.pcolormesh(lats, lons, data_masked.transpose())
    else:
        plt.pcolormesh(lats, lons, data_masked)
    plt.colorbar()
    plt.show()

    data_masked = np.reshape(data_masked, (len(lats) * len(lons),))

    # Repeat the latitudes and tile the longitudes so that lat_masked[i], lon_masked[i] corresponds to data[i].
    if repeat0tile1:
        lat_masked = np.repeat(lats, len(lons))
        lon_masked = np.tile(lons, len(lats))
    else:
        lat_masked = np.tile(lats, len(lons))
        lon_masked = np.repeat(lons, len(lats))

    # Mask the latitudes and longitudes that correspond to masked data values.
    lat_masked = np.ma.masked_where(np.ma.getmask(data_masked), lat_masked)
    lon_masked = np.ma.masked_where(np.ma.getmask(data_masked), lon_masked)

    # Use the mask to remove all masked elements as griddata ignores masked data and cannot deal with NaN values.
    lat_masked = lat_masked[~lat_masked.mask]
    lon_masked = lon_masked[~lon_masked.mask]
    data_masked = data_masked[~data_masked.mask]

    if convert_lon_range:
        lon_min, lon_max = convert_lon_range_to_0360(lon_min, lon_max)

    # Create grid of points we wish to evaluate the interpolation on.
    if polar_stereographic_grid:
        x_min = lats.min()
        x_max = lats.max()
        y_min = lons.min()
        y_max = lons.max()
        latgrid_interp, longrid_interp = np.mgrid[x_min:x_max:1000*1j, y_min:y_max:1000*1j]
    else:
        latgrid_interp, longrid_interp = np.mgrid[lat_min:lat_max:n_lat*1j, lon_min:lon_max:n_lon*1j]

    logger.info('Data masked in preparation for interpolation.')
    logger.info('Masked latitude grid: min={:.2f}, max={:.2f}, shape={}'
                .format(lat_masked.min(), lat_masked.max(), lat_masked.shape))
    logger.info('Masked longitude grid: min={:.2f}, max={:.2f}, shape={}'
                .format(lon_masked.min(), lon_masked.max(), lon_masked.shape))
    logger.info('Masked data grid: min={:.2f}, max={:.2f}, shape={}'
                .format(data_masked.min(), data_masked.max(), data_masked.shape))
    logger.info('Latitude interpolation grid: min={:.2f}, max={:.2f}, shape={}'
                .format(latgrid_interp.min(), latgrid_interp.max(), latgrid_interp.shape))
    logger.info('Longitude interpolation grid: min={:.2f}, max={:.2f}, shape={}'
                .format(longrid_interp.min(), longrid_interp.max(), longrid_interp.shape))

    logger.info('Interpolating dataset...')
    data_interp = griddata((lat_masked, lon_masked), data_masked, (latgrid_interp, longrid_interp),
                           method=interp_method)

    logger.info('Plotting interpolated data.')
    import matplotlib.pyplot as plt
    plt.pcolormesh(latgrid_interp, longrid_interp, data_interp)
    plt.colorbar()
    plt.show()

    # Since we get back interpolated values over the land, we must mask them or get rid of them. We do this by
    # looping through the interpolated values and mask values that are supposed to be land by setting their value to
    # np.nan. We do this by comparing each interpolated value mdt_interp[i][j] with the mdt_values value that is
    # closest in latitude and longitude.
    # We can also compute the residuals, that is the error between the interpolated values and the actual values
    # which should be zero where an interpolation gridpoint coincides with an original gridpoint, and should be
    # pretty small everywhere else.
    logger.info('Masking invalid values in the interpolated grid...')
    residual = np.zeros(data_interp.shape)
    for i in range(latgrid_interp.shape[0]):
        for j in range(latgrid_interp.shape[1]):
            lat = latgrid_interp[i][j]
            lon = longrid_interp[i][j]
            closest_lat_idx = np.abs(lats - lat).argmin()
            closest_lon_idx = np.abs(lons - lon).argmin()

            if repeat0tile1:
                closest_data = data[closest_lat_idx][closest_lon_idx]
            else:
                closest_data = data[closest_lon_idx][closest_lat_idx]

            if mask_value_cond(closest_data) or mask_value_cond(data_interp[i][j]):
                data_interp[i][j] = np.nan
                residual[i][j] = np.nan
            else:
                residual[i][j] = data_interp[i][j] - closest_data

    logger.info('Plotting masked interpolated data.')
    import matplotlib.pyplot as plt
    latgrid_interp = np.ma.masked_where(np.isnan(latgrid_interp), latgrid_interp)
    longrid_interp = np.ma.masked_where(np.isnan(longrid_interp), longrid_interp)
    data_interp = np.ma.masked_where(np.isnan(data_interp), data_interp)
    plt.pcolormesh(latgrid_interp, longrid_interp, data_interp)
    plt.colorbar()
    plt.show()

    logger.info('Plotting interpolated data residual.')
    import matplotlib.pyplot as plt
    residual = np.ma.masked_where(np.isnan(residual), residual)
    plt.pcolormesh(latgrid_interp, longrid_interp, residual)
    plt.colorbar()
    plt.show()

    logger.info('Interpolating dataset... DONE!')

    # We only need to store the list of lats and lons used.
    latgrid_interp = latgrid_interp[:, 0]
    longrid_interp = longrid_interp[0]

    # Pickle the interpolated grid as a form of memoization to avoid having to recompute it again for the same
    # gridpoints.
    # with open(pickle_filepath, 'wb') as f:
    #     logger.info('Pickling interpolated grid: {:s}'.format(pickle_filepath))
    #     data_interp_dict = {
    #         'data_interp': data_interp,
    #         'latgrid_interp': latgrid_interp,
    #         'longrid_interp': longrid_interp
    #     }
    #     pickle.dump(data_interp_dict, f, pickle.HIGHEST_PROTOCOL)

    return data_interp, latgrid_interp, longrid_interp