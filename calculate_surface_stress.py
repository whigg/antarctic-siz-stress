# TODO: Use the typing module.
# TODO: Use propoer docstrings for functions.
# TODO: Estimate tau_error? Can you? NCEP Reanalysis doesn't really provide a "measurement error".
# TODO: Output more statistics during the analysis?
# TODO: Plot everything but draw the ice line where alpha drops below 0.15.
# TODO: Plot the zero stress line. We expect a unique position for it right?

# Conventions
# Latitude = -90 (90 S) to +90 (90 N)
# Longitude = -180 (180 W) to 180 (180 E)

import datetime
import calendar

import numpy as np
from joblib import Parallel, delayed

# Configure logger first before importing any sub-module that depend on the logger being already configured.
import logging.config

logging.config.fileConfig('logging.ini')
logger = logging.getLogger(__name__)

np.set_printoptions(precision=4)


def check_distances():
    """ Double checking some distances. """
    from utils import distance
    logger.info('distance(-89.999, 0, -89.999, 180) = {}'.format(distance(-89.999, 0, -89.999, 180)))
    logger.info('2*distance(0, 0, 0, 180) = {}'.format(2 * distance(0, 0, 0, 180)))
    logger.info('distance(-80, 74, -80, 74.5) = {}'.format(distance(-80, 74, -80, 74.5)))
    logger.info('distance(-80, 74.5, -80, 74) = {}'.format(distance(-80, 74.5, -80, 74)))
    logger.info('distance(-80, 74, -80.5, 74) = {}'.format(distance(-80, 74, -80.5, 74)))
    logger.info('distance(-80.5, 74, -80, 74) = {}'.format(distance(-80.5, 74, -80, 74)))


def check_sea_ice_motion_field():
    """ Making sure that sea ice motion fields interpolate properly. """
    from SeaIceMotionDataset import SeaIceMotionDataset
    sic = SeaIceMotionDataset(datetime.date(2015, 7, 16))
    sic.plot_sea_ice_motion_vector_field()


def process_day(date):
    """ Process for only one day. """
    from SurfaceStressDataWriter import SurfaceStressDataWriter

    try:
        surface_stress_dataset = SurfaceStressDataWriter(date)

        surface_stress_dataset.compute_daily_surface_stress_field()
        surface_stress_dataset.compute_daily_ekman_pumping_field()
        surface_stress_dataset.write_fields_to_netcdf(field_type='daily')

    except Exception as e:
        logger.error('Failed to process day {}. Returning.'.format(date))
        logger.error('{}'.format(e), exc_info=True)
        return


def process_and_plot_day(date):
    """ Process and plot fields for only one day. """
    from SurfaceStressDataWriter import SurfaceStressDataWriter
    surface_stress_dataset = SurfaceStressDataWriter(date)

    surface_stress_dataset.compute_daily_surface_stress_field()
    surface_stress_dataset.compute_daily_ekman_pumping_field()
    surface_stress_dataset.write_fields_to_netcdf(field_type='daily')
    surface_stress_dataset.plot_diagnostic_fields(plot_type='daily', custom_label='no_custom_label_', avg_period='00')


def plot_day(date):
    from SurfaceStressDataWriter import SurfaceStressDataWriter
    surface_stress_dataset = SurfaceStressDataWriter(None)
    surface_stress_dataset.date = date
    surface_stress_dataset.compute_mean_fields([date], avg_method='full_data_only')
    surface_stress_dataset.plot_diagnostic_fields(plot_type='daily')


def process_month(date_in_month):
    """ Process one month and produce a monthly average. """
    from utils import date_range

    year = date_in_month.year
    month = date_in_month.month

    n_days = calendar.monthrange(year, month)[1]
    dates = date_range(datetime.date(year, month, 1), datetime.date(year, month, n_days))

    Parallel(n_jobs=5)(delayed(process_day)(datetime.date(year, month, day)) for day in range(1, n_days + 1))

    surface_stress_dataset = SurfaceStressDataWriter(None)
    surface_stress_dataset.date = date_in_month
    surface_stress_dataset.compute_mean_fields(dates, avg_method='partial_data_ok')
    surface_stress_dataset.plot_diagnostic_fields(plot_type='monthly')
    surface_stress_dataset.write_fields_to_netcdf(field_type='monthly')


def process_year(date_in_year):
    """ Process an entire year and produce an annual mean. """

    year = date_in_year.year

    for month in range(1, 13):
        process_month(datetime.date(year, month, 1))

    produce_annual_mean(date_in_year)


def produce_monthly_mean(date_in_month):
    from utils import date_range

    month = date_in_month.month
    year = date_in_month.year

    date1 = datetime.date(year, month, 1)
    n_days = calendar.monthrange(date1.year, date1.month)[1]
    date2 = datetime.date(year, month, n_days)
    dates = date_range(date1, date2)

    surface_stress_dataset = SurfaceStressDataWriter(None)
    surface_stress_dataset.date = date1
    surface_stress_dataset.compute_mean_fields(dates, avg_method='partial_data_ok')
    surface_stress_dataset.plot_diagnostic_fields(plot_type='monthly')
    surface_stress_dataset.write_fields_to_netcdf(field_type='monthly')


def produce_annual_mean(year):
    from utils import get_netCDF_filepath

    dates = date_range(datetime.date(year, 1, 1), datetime.date(year, 12, 31))

    tau_filepath = get_netCDF_filepath(field_type='annual', date=dates[0])

    surface_stress_dataset = SurfaceStressDataWriter(None)
    surface_stress_dataset.date = dates[0]
    surface_stress_dataset.compute_mean_fields(dates, avg_method='partial_data_ok', tau_filepath=tau_filepath)
    surface_stress_dataset.plot_diagnostic_fields(plot_type='annual')
    surface_stress_dataset.write_fields_to_netcdf(field_type='annual')


def produce_seasonal_mean(seasons_to_compute, year):
    seasons = {
        'JFM': {'date1': datetime.date(year, 1, 1),
                'date2': datetime.date(year, 3, 31),
                'label': 'Summer_JFM_' + str(year) + '_average'},
        'AMJ': {'date1': datetime.date(year, 4, 1),
                'date2': datetime.date(year, 6, 30),
                'label': 'Fall_AMJ_' + str(year) + '_average'},
        'JAS': {'date1': datetime.date(year, 7, 1),
                'date2': datetime.date(year, 9, 30),
                'label': 'Winter_JAS_' + str(year) + '_average'},
        'OND': {'date1': datetime.date(year, 10, 1),
                'date2': datetime.date(year, 12, 31),
                'label': 'Spring_JFM_' + str(year) + '_average'}
    }

    for s in seasons_to_compute:
        logger.info('s={:s}'.format(s))
        dates = date_range(seasons[s]['date1'], seasons[s]['date2'])

        surface_stress_dataset = SurfaceStressDataWriter(None)
        surface_stress_dataset.date = dates[0]
        surface_stress_dataset.compute_mean_fields(dates, avg_method='partial_data_ok')
        surface_stress_dataset.plot_diagnostic_fields(plot_type='custom', custom_label=seasons[s]['label'])
        surface_stress_dataset.write_fields_to_netcdf(field_type='seasonal', season_str=s)

    # Process summer (DJF) separately.
    # dec = date_range(datetime.date(year - 1, 12, 1), datetime.date(year - 1, 12, 31))
    # janfeb = date_range(datetime.date(year, 1, 1), datetime.date(year, 2, 28))  # TODO: Feb 29
    # dates = dec + janfeb
    # custom_label = 'Summer_DJF_' + str(year - 1) + '-' + str(year) + '_average'
    #
    # surface_stress_dataset = SurfaceStressDataWriter(None)
    # surface_stress_dataset.date = dates[0]
    # surface_stress_dataset.compute_mean_fields(dates, avg_method='partial_data_ok')
    # surface_stress_dataset.plot_diagnostic_fields(plot_type='custom', custom_label=custom_label)
    # surface_stress_dataset.write_fields_to_netcdf(field_type='seasonal')


def process_multiple_years(year_start, year_end):
    for year in range(year_end, year_start - 1, -1):
        for month in range(1, 13):
            n_days = calendar.monthrange(year, month)[1]
            Parallel(n_jobs=12)(delayed(process_day)(datetime.date(year, month, day)) for day in range(1, n_days + 1))

            # try:
            #     Parallel(n_jobs=12)(delayed(process_day)(datetime.date(date_in_month.year, date_in_month.month, day))
            #                         for day in range(1, n_days+1))
            # except Exception as e:
            #     logger.error('{}'.format(e), exc_info=True)
            #     continue


def produce_seasonal_climatology(seasons, year_start, year_end):
    year_range = str(year_start) + '-' + str(year_end)

    labels = {
        'DJF': 'Summer_DJF_' + year_range + '_average',
        'MAM': 'Fall_MAM_' + year_range + '_average',
        'JJA': 'Winter_JJA_' + year_range + '_average',
        'SON': 'Spring_SON_' + year_range + '_average',
        'JFM': 'Summer_JFM_' + year_range + '_average',
        'AMJ': 'Fall_AMJ_' + year_range + '_average',
        'JAS': 'Winter_JAS_' + year_range + '_average',
        'OND': 'Spring_OND_' + year_range + '_average'
    }

    season_start_month = {
        'DJF': 12,
        'MAM': 3,
        'JJA': 6,
        'SON': 9,
        'JFM': 1,
        'AMJ': 4,
        'JAS': 7,
        'OND': 10
    }

    season_end_month = {
        'DJF': 2,
        'MAM': 5,
        'JJA': 8,
        'SON': 11,
        'JFM': 3,
        'AMJ': 6,
        'JAS': 9,
        'OND': 12
    }

    for season in seasons:
        season_days = []

        for year in range(year_start, year_end + 1):
            start_date = datetime.date(year, season_start_month[season], 1)

            end_month_days = calendar.monthrange(year, season_end_month[season])[1]
            end_date = datetime.date(year, season_end_month[season], end_month_days)

            season_days = season_days + date_range(start_date, end_date)

        from utils import get_netCDF_filepath
        tau_fp = get_netCDF_filepath(field_type='seasonal_climo', season_str=season, year_start=year_start, year_end=year_end)

        surface_stress_dataset = SurfaceStressDataWriter(None)
        surface_stress_dataset.date = season_days[-1]
        surface_stress_dataset.compute_mean_fields(season_days, avg_method='partial_data_ok', tau_filepath=tau_fp)
        surface_stress_dataset.plot_diagnostic_fields(plot_type='custom', custom_label=labels[season])
        surface_stress_dataset.write_fields_to_netcdf(field_type='seasonal_climo', season_str=season,
                                                      year_start=year_start, year_end=year_end)


def produce_monthly_climatology(months, year_start, year_end):
    import calendar

    year_range = str(year_start) + '-' + str(year_end)

    for month in months:
        label = calendar.month_abbr[month] + '_' + year_range + '_average'

        month_days = []
        for year in range(year_start, year_end + 1):
            n_days = calendar.monthrange(year, month)[1]
            month_days = month_days + date_range(datetime.date(year, month, 1), datetime.date(year, month, n_days))

        avg_period = str(month).zfill(2)

        surface_stress_dataset = SurfaceStressDataWriter(None)
        surface_stress_dataset.date = month_days[-1]
        surface_stress_dataset.compute_mean_fields(month_days, avg_method='partial_data_ok')
        surface_stress_dataset.plot_diagnostic_fields(plot_type='custom', custom_label=label, avg_period=avg_period)
        surface_stress_dataset.write_fields_to_netcdf(field_type='monthly_climo', year_start=year_start,
                                                      year_end=year_end)


def produce_climatology(year_start, year_end):
    from utils import get_netCDF_filepath

    climo_label = str(year_start) + '-' + str(year_end) + '_average'
    tau_filepath = get_netCDF_filepath(field_type='climo', year_start=year_start, year_end=year_end)

    dates = date_range(datetime.date(year_start, 1, 1), datetime.date(year_end, 12, 31))

    surface_stress_dataset = SurfaceStressDataWriter(None)
    surface_stress_dataset.date = dates[0]
    surface_stress_dataset.compute_mean_fields(dates, avg_method='partial_data_ok', tau_filepath=tau_filepath)
    surface_stress_dataset.plot_diagnostic_fields(plot_type='custom', custom_label=climo_label, avg_period='00')
    surface_stress_dataset.write_fields_to_netcdf(field_type='climo', year_start=year_start, year_end=year_end)


def process_neutral_density_field(time_span, avg_period, grid_size, field_type, depth_level):
    from NeutralDensityDataset import NeutralDensityDataset

    try:
        NeutralDensityDataset(time_span, avg_period, grid_size, field_type, depth_level)
    except Exception as e:
        logger.error('Failed to process neutral density ({}, {}, {}, {}, {}). Returning.'
                     .format(time_span, avg_period, grid_size, field_type, depth_level))
        logger.error('{}'.format(e), exc_info=True)
        return


def process_neutral_density_fields_multiple_depths(time_span, avg_period, grid_size, field_type, depth_levels):
    n_jobs = len(depth_levels)
    Parallel(n_jobs=n_jobs)(delayed(process_neutral_density_field)(time_span, avg_period, grid_size, field_type, lvl)
                            for lvl in depth_levels)


def plot_meridional_salinity_profiles(time_span, grid_size, field_type, lon, split_depth):
    import os

    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter
    import cmocean.cm

    from SalinityDataset import SalinityDataset
    from constants import output_dir_path

    image_filepaths = []

    for avg_period in ['00', '13', '14', '15', '16']:
        salinity_dataset = SalinityDataset(time_span, avg_period, grid_size, field_type)
        lats, depths, salinity_profile = salinity_dataset.meridional_salinity_profile(lon=lon, lat_min=-80, lat_max=0)

        time_span_str = time_span
        if time_span == 'A5B2':
            time_span_str = '2005-12'
        elif time_span == '95A4':
            time_span_str = '1995-2004'

        avg_period_str = avg_period
        if avg_period == '00':
            avg_period_str = 'mean'
        elif avg_period == '13':
            avg_period_str = 'JFM-seasonal'
        elif avg_period == '14':
            avg_period_str = 'AMJ-seasonal'
        elif avg_period == '15':
            avg_period_str = 'JAS-seasonal'
        elif avg_period == '16':
            avg_period_str = 'OND-seasonal'

        title_str = time_span_str + '-' + avg_period_str + '-lon=' + str(int(lon))

        fig, (ax1, ax2) = plt.subplots(2)

        levels = np.linspace(33.8, 36, 21)
        idx_split_depth = np.abs(depths - split_depth).argmin()

        im1 = ax1.contourf(lats, depths[:idx_split_depth], salinity_profile[:idx_split_depth, :],
                             cmap=cmocean.cm.haline, colors=None, vmin=33.8, vmax=36, levels=levels, extend='both')
        im2 = ax2.contourf(lats, depths[idx_split_depth:], salinity_profile[idx_split_depth:, :],
                             cmap=cmocean.cm.haline, colors=None, vmin=33.8, vmax=36, levels=levels, extend='both')

        # plt.xticks(list(plt.xticks()[0]) + [split_depth])

        idx_40S = np.nanargmin(np.abs(lats - -40))
        idx_80S = np.nanargmin(np.abs(lats - -80))
        idx_min_salinity = np.nanargmin(salinity_profile[0, idx_80S:idx_40S]) + idx_80S
        lat_min_salinity = lats[idx_min_salinity]
        ax1.plot([lat_min_salinity, lat_min_salinity], [0, 50], 'red', lw=2)
        ax1.text(lat_min_salinity + 0.5, 30, '{:.1f}°'.format(lat_min_salinity), fontsize=10, color='red')

        ax1.set_title(title_str, y=1.15, fontsize=12)

        fig.subplots_adjust(left=0.10, bottom=0.20, right=0.95, top=0.9, hspace=0)
        cbar_ax = fig.add_axes([0.15, 0.1, 0.7, 0.05])
        clb = fig.colorbar(im1, cax=cbar_ax, extend='both', orientation='horizontal')
        clb.ax.set_title('salinity (g/kg)', fontsize=12)

        ax1.set_ylim(0, depths[idx_split_depth - 1])
        ax2.set_ylim(depths[idx_split_depth], 5000)
        ax1.set_xlim(-75, 0)
        ax2.set_xlim(-75, 0)
        ax1.invert_yaxis()
        ax2.invert_yaxis()

        ax1.spines['bottom'].set_visible(False)
        ax2.spines['top'].set_visible(False)

        ax2.xaxis.set_tick_params(which='both', bottom=False, labelbottom=False)
        ax1.xaxis.tick_top()
        ax1.xaxis.set_major_formatter(FormatStrFormatter('%d°'))

        # plt.subplot_tool()
        # plt.show()

        png_filename = 'salinity_profile_woa13_' + time_span + '_' + avg_period + '_' + grid_size + '_' + \
                       'lon' + str(int(lon))
        png_filepath = os.path.join(output_dir_path, 'salinity_profiles', png_filename + '.png')

        image_filepaths.append(png_filepath)

        dir = os.path.dirname(png_filepath)
        if not os.path.exists(dir):
            logger.info('Creating directory: {:s}'.format(dir))
            os.makedirs(dir)

        logger.info('Saving salinity profile: {:s}'.format(png_filepath))
        plt.savefig(png_filepath, dpi=300, format='png', transparent=False, bbox_inches='tight')

    from PIL import Image

    images = []
    for fp in image_filepaths:
        images.append(Image.open(fp, 'r'))

    widths, heights = zip(*(i.size for i in images))

    w = widths[0]
    h = heights[0]

    new_im = Image.new('RGB', (3*w, 2*h), color=(255, 255, 255))

    new_im.paste(images[1], (0, 0))
    new_im.paste(images[2], (w, 0))
    new_im.paste(images[3], (0, h))
    new_im.paste(images[4], (w, h))
    new_im.paste(images[0], (2*w, int(np.ceil(0.5*h))))

    all_filename = 'salinity_profile_woa13_' + time_span + '_all_' + grid_size + '_' + 'lon' + str(int(lon))
    all_filepath = os.path.join(output_dir_path, 'salinity_profiles', all_filename + '.png')

    logger.info('Saving combined salinity profiles: {:s}'.format(all_filepath))
    new_im.save(all_filepath)


def plot_meridional_temperature_profiles(time_span, grid_size, field_type, lon, split_depth):
    import os

    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter
    import cmocean.cm

    from TemperatureDataset import TemperatureDataset
    from constants import output_dir_path

    image_filepaths = []

    for avg_period in ['00', '13', '14', '15', '16']:
        temperature_dataset = TemperatureDataset(time_span, avg_period, grid_size, field_type)
        lats, depths, temperature_profile = temperature_dataset.meridional_temperature_profile(lon=lon, lat_min=-80, lat_max=0)

        time_span_str = time_span
        if time_span == 'A5B2':
            time_span_str = '2005-12'
        elif time_span == '95A4':
            time_span_str = '1995-2004'

        avg_period_str = avg_period
        if avg_period == '00':
            avg_period_str = 'mean'
        elif avg_period == '13':
            avg_period_str = 'JFM-seasonal'
        elif avg_period == '14':
            avg_period_str = 'AMJ-seasonal'
        elif avg_period == '15':
            avg_period_str = 'JAS-seasonal'
        elif avg_period == '16':
            avg_period_str = 'OND-seasonal'

        title_str = time_span_str + '-' + avg_period_str + '-lon=' + str(int(lon))

        fig, (ax1, ax2) = plt.subplots(2)

        idx_split_depth = np.abs(depths - split_depth).argmin()

        im1 = ax1.pcolormesh(lats, depths[:idx_split_depth], temperature_profile[:idx_split_depth, :],
                             cmap=cmocean.cm.thermal, vmin=-2, vmax=2)
        im2 = ax2.pcolormesh(lats, depths[idx_split_depth:], temperature_profile[idx_split_depth:, :],
                             cmap=cmocean.cm.thermal, vmin=-2, vmax=2)

        # idx_40S = np.abs(lats - -40).argmin()
        # idx_60S = np.abs(lats - -60).argmin()
        # idx_max_temperature = temperature_profile[0, idx_60S:idx_40S].argmin() + idx_60S
        # lat_max_temperature = lats[idx_max_temperature]
        # ax1.plot([lat_max_temperature, lat_max_temperature], [0, 50], 'red', lw=2)
        # ax1.text(lat_max_temperature + 0.5, 30, '{:.1f}°'.format(lat_max_temperature), fontsize=10, color='red')

        ax1.set_title(title_str, y=1.15, fontsize=12)

        fig.subplots_adjust(left=0.10, bottom=0.20, right=0.95, top=0.9, hspace=0)
        cbar_ax = fig.add_axes([0.15, 0.1, 0.7, 0.05])
        clb = fig.colorbar(im1, cax=cbar_ax, extend='both', orientation='horizontal')
        clb.ax.set_title('temperature (g/kg)', fontsize=12)

        ax1.set_ylim(0, depths[idx_split_depth - 1])
        ax2.set_ylim(depths[idx_split_depth], 5000)
        ax1.set_xlim(-70, 0)
        ax2.set_xlim(-70, 0)
        ax1.invert_yaxis()
        ax2.invert_yaxis()

        ax1.spines['bottom'].set_visible(False)
        ax2.spines['top'].set_visible(False)

        ax2.xaxis.set_tick_params(which='both', bottom=False, labelbottom=False)
        ax1.xaxis.tick_top()
        ax1.xaxis.set_major_formatter(FormatStrFormatter('%d°'))

        # plt.subplot_tool()
        # plt.show()

        png_filename = 'temperature_profile_woa13_' + time_span + '_' + avg_period + '_' + grid_size + '_' + \
                       'lon' + str(int(lon))
        png_filepath = os.path.join(output_dir_path, 'temperature_profiles', png_filename + '.png')

        image_filepaths.append(png_filepath)

        dir = os.path.dirname(png_filepath)
        if not os.path.exists(dir):
            logger.info('Creating directory: {:s}'.format(dir))
            os.makedirs(dir)

        logger.info('Saving temperature profile: {:s}'.format(png_filepath))
        plt.savefig(png_filepath, dpi=300, format='png', transparent=False, bbox_inches='tight')

    from PIL import Image

    images = []
    for fp in image_filepaths:
        images.append(Image.open(fp, 'r'))

    widths, heights = zip(*(i.size for i in images))

    w = widths[0]
    h = heights[0]

    new_im = Image.new('RGB', (3*w, 2*h), color=(255, 255, 255))

    new_im.paste(images[1], (0, 0))
    new_im.paste(images[2], (w, 0))
    new_im.paste(images[3], (0, h))
    new_im.paste(images[4], (w, h))
    new_im.paste(images[0], (2*w, int(np.ceil(0.5*h))))

    all_filename = 'temperature_profile_woa13_' + time_span + '_all_' + grid_size + '_' + 'lon' + str(int(lon))
    all_filepath = os.path.join(output_dir_path, 'temperature_profiles', all_filename + '.png')

    logger.info('Saving combined temperature profiles: {:s}'.format(all_filepath))
    new_im.save(all_filepath)


def plot_meridional_gamma_profiles(time_span, grid_size, field_type, lon, split_depth):
    import os

    import matplotlib.pyplot as plt
    from matplotlib.ticker import FormatStrFormatter
    import cmocean.cm

    from NeutralDensityDataset import NeutralDensityDataset
    from constants import output_dir_path

    image_filepaths = []

    for avg_period in ['00']:
        gamma_dataset = NeutralDensityDataset(time_span, avg_period, grid_size, field_type, depth_levels=np.arange(100))
        lats, depths, gamma_profile = gamma_dataset.meridional_gamma_profile(lon=lon, lat_min=-80, lat_max=-40)

        depths = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100,
                  125, 150, 175, 200, 225, 250, 275, 300, 325, 350, 375, 400, 425, 450, 475, 500,
                  550, 600, 650, 700, 750, 800, 850, 900, 950, 1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350, 1400,
                  1450, 1500, 1550, 1600, 1650, 1700, 1750, 1800, 1850, 1900, 1950, 2000,
                  2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000, 3100, 3200, 3300, 3400, 3500, 3600, 3700,
                  3800, 3900, 4000, 4100, 4200, 4300, 4400, 4500, 4600, 4700, 4800, 4900, 5000, 5100, 5200, 5300]
        depths = np.array(depths)

        time_span_str = time_span
        if time_span == 'A5B2':
            time_span_str = '2005-12'
        elif time_span == '95A4':
            time_span_str = '1995-2004'

        avg_period_str = avg_period
        if avg_period == '00':
            avg_period_str = 'mean'
        elif avg_period == '13':
            avg_period_str = 'JFM-seasonal'
        elif avg_period == '14':
            avg_period_str = 'AMJ-seasonal'
        elif avg_period == '15':
            avg_period_str = 'JAS-seasonal'
        elif avg_period == '16':
            avg_period_str = 'OND-seasonal'

        title_str = time_span_str + '-' + avg_period_str + '-lon=' + str(int(lon))

        fig, (ax1, ax2) = plt.subplots(2)

        levels = np.linspace(26.6, 28, 21)
        idx_split_depth = np.abs(depths - split_depth).argmin()

        im1 = ax1.contourf(lats, depths[:idx_split_depth], gamma_profile[:idx_split_depth, :],
                             cmap=cmocean.cm.dense, colors=None, vmin=26.6, vmax=28, levels=levels, extend='both')
        im2 = ax2.contourf(lats, depths[idx_split_depth:], gamma_profile[idx_split_depth:, :],
                             cmap=cmocean.cm.dense, colors=None, vmin=26.6, vmax=28, levels=levels, extend='both')

        # plt.xticks(list(plt.xticks()[0]) + [split_depth])

        idx_40S = np.nanargmin(np.abs(lats - -40))
        idx_80S = np.nanargmin(np.abs(lats - -80))
        idx_min_gamma = np.nanargmax(gamma_profile[0, idx_80S:idx_40S]) + idx_80S
        lat_min_gamma = lats[idx_min_gamma]
        ax1.plot([lat_min_gamma, lat_min_gamma], [0, 50], 'red', lw=2)
        ax1.text(lat_min_gamma + 0.5, 30, '{:.1f}°'.format(lat_min_gamma), fontsize=10, color='red')

        ax1.set_title(title_str, y=1.15, fontsize=12)

        fig.subplots_adjust(left=0.10, bottom=0.20, right=0.95, top=0.9, hspace=0)
        cbar_ax = fig.add_axes([0.15, 0.1, 0.7, 0.05])
        clb = fig.colorbar(im1, cax=cbar_ax, extend='both', orientation='horizontal')
        clb.ax.set_title('gamma_n (kg/m$^3$)', fontsize=12)

        ax1.set_ylim(0, depths[idx_split_depth - 1])
        ax2.set_ylim(depths[idx_split_depth], 5000)
        ax1.set_xlim(-75, -40)
        ax2.set_xlim(-75, -40)
        ax1.invert_yaxis()
        ax2.invert_yaxis()

        ax1.spines['bottom'].set_visible(False)
        ax2.spines['top'].set_visible(False)

        ax2.xaxis.set_tick_params(which='both', bottom=False, labelbottom=False)
        ax1.xaxis.tick_top()
        ax1.xaxis.set_major_formatter(FormatStrFormatter('%d°'))

        # plt.subplot_tool()
        # plt.show()

        png_filename = 'gamma_profile_woa13_' + time_span + '_' + avg_period + '_' + grid_size + '_' + \
                       'lon' + str(int(lon))
        png_filepath = os.path.join(output_dir_path, 'gamma_profiles', png_filename + '.png')

        image_filepaths.append(png_filepath)

        dir = os.path.dirname(png_filepath)
        if not os.path.exists(dir):
            logger.info('Creating directory: {:s}'.format(dir))
            os.makedirs(dir)

        logger.info('Saving gamma profile: {:s}'.format(png_filepath))
        plt.savefig(png_filepath, dpi=300, format='png', transparent=False, bbox_inches='tight')

    # from PIL import Image
    #
    # images = []
    # for fp in image_filepaths:
    #     images.append(Image.open(fp, 'r'))
    #
    # widths, heights = zip(*(i.size for i in images))
    #
    # w = widths[0]
    # h = heights[0]
    #
    # new_im = Image.new('RGB', (3*w, 2*h), color=(255, 255, 255))
    #
    # new_im.paste(images[1], (0, 0))
    # new_im.paste(images[2], (w, 0))
    # new_im.paste(images[3], (0, h))
    # new_im.paste(images[4], (w, h))
    # new_im.paste(images[0], (2*w, int(np.ceil(0.5*h))))
    #
    # all_filename = 'gamma_profile_woa13_' + time_span + '_all_' + grid_size + '_' + 'lon' + str(int(lon))
    # all_filepath = os.path.join(output_dir_path, 'gamma_profiles', all_filename + '.png')
    #
    # logger.info('Saving combined gamma profiles: {:s}'.format(all_filepath))
    # new_im.save(all_filepath)


def look_at_neutral_density_contours(year_start, year_end):
    # Just looking at the surface neutral density for A5B2.
    for avg_period in ['00']:  # '['13', '14', '15', '16', '00']:
        dates = []
        for year in range(year_start, year_end+1):
            if avg_period == '00' or avg_period == '13':
                dates = dates + date_range(datetime.date(year, 1, 1), datetime.date(year, 3, 31))
            if avg_period == '00' or avg_period == '14':
                dates = dates + date_range(datetime.date(year, 4, 1), datetime.date(year, 6, 30))
            if avg_period == '00' or avg_period == '15':
                dates = dates + date_range(datetime.date(year, 7, 1), datetime.date(year, 9, 30))
            if avg_period == '00' or avg_period == '16':
                dates = dates + date_range(datetime.date(year, 10, 1), datetime.date(year, 12, 31))

        custom_label = ''
        if avg_period == '00':
            custom_label = str(year_start) + '-' + str(year_end) + '_climo'
        elif avg_period == '13':
            custom_label = str(year_start) + '-' + str(year_end) + '_seasonal_JFM'
        elif avg_period == '14':
            custom_label = str(year_start) + '-' + str(year_end) + '_seasonal_AMJ'
        elif avg_period == '15':
            custom_label = str(year_start) + '-' + str(year_end) + '_seasonal_JAS'
        elif avg_period == '16':
            custom_label = str(year_start) + '-' + str(year_end) + '_seasonal_OND'

        surface_stress_dataset = SurfaceStressDataWriter(None)
        surface_stress_dataset.date = dates[-1]
        surface_stress_dataset.compute_mean_fields(dates, avg_method='partial_data_ok')
        surface_stress_dataset.plot_diagnostic_fields(plot_type='custom', custom_label=custom_label, avg_period=avg_period)


def analyze_zero_zonal_stress_line(custom_str=None):
    import os
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import cartopy
    import cartopy.crs as ccrs
    from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter

    from utils import get_netCDF_filepath, get_northward_zero_zonal_stress_line, get_northward_ice_edge
    from constants import output_dir_path, lon_min, lon_max, n_lon

    surface_stress_dir = os.path.join(output_dir_path, 'surface_stress')

    years = np.arange(2000, 2016, 1)

    lon_bins = np.linspace(lon_min, lon_max, n_lon)
    lat_northward = np.empty((len(lon_bins), len(years)))
    lat_northward[:] = -180
    ice_lat_northward = np.empty((len(lon_bins), len(years)))
    ice_lat_northward[:] = -180

    land_50m = cartopy.feature.NaturalEarthFeature('physical', 'land', '10m', edgecolor='face',
                                                   facecolor='dimgray', linewidth=0)
    vector_crs = ccrs.PlateCarree()
    fig = plt.figure(figsize=(16, 9))

    ax = fig.add_subplot(111, projection=ccrs.SouthPolarStereo())
    ax.add_feature(land_50m)
    ax.set_extent([-110, -50, -75, -65], ccrs.PlateCarree())
    patches = []

    NUM_COLORS = len(years)
    cm = plt.get_cmap('PiYG')
    ax.set_color_cycle([cm(1. * i / NUM_COLORS) for i in range(NUM_COLORS)])

    for i in range(len(years)):
        year = years[i]

        tau_filepath = get_netCDF_filepath(date=datetime.date(year, 1, 1), field_type='annual')
        # tau_filepath = get_netCDF_filepath(field_type='seasonal', date=datetime.date(year, 1, 1), season_str='JFM')

        # lons, lats = get_zero_zonal_stress_line(tau_filepath)
        lon_bins, lat_northward_i = get_northward_zero_zonal_stress_line(tau_filepath)
        lat_northward[:, i] = lat_northward_i

        bellinghausen = np.logical_and(lon_bins > -150, lon_bins < -30)

        logger.info('({:d}) lat_max={:f}'.format(year, np.nanmax(lat_northward[:, i])))

        # ice_lon_bins, ice_lat_northward_i = get_northward_ice_edge(tau_filepath)
        # ice_lat_northward[:, i] = ice_lat_northward_i

        # plt.plot(lon_bins, lat_northward_i, label=str(year), color=cm(1. * i/NUM_COLORS))
        # plt.plot(ice_lon_bins, ice_lat_northward_i, color=cm(1. * i/NUM_COLORS))

        ax.plot(lon_bins[bellinghausen], lat_northward_i[bellinghausen], color=cm(1. * i/NUM_COLORS), linewidth=1, label=str(year), transform=vector_crs)
        # p = ax.plot(ice_lon_bins, ice_lat_northward_i, linewidth=1, label=str(year), transform=vector_crs)
        patches = patches + [mpatches.Patch(color=cm(1. * i/NUM_COLORS), label=str(year))]

    ax.grid()

    # ax.legend()
    plt.legend(handles=patches, loc='upper right', bbox_to_anchor=(1.03, 1), ncol=1, mode='expand', frameon=False,
               borderaxespad=0)
    plt.savefig('tau_x_zero_line' + custom_str + '.png', dpi=600, format='png', transparent=False, bbox_inches='tight')
    plt.show()
    plt.close()

    from scipy import stats

    slopes = np.zeros(len(lon_bins))
    intercepts = np.zeros(len(lon_bins))
    r_values = np.zeros(len(lon_bins))
    p_values = np.zeros(len(lon_bins))
    std_errs = np.zeros(len(lon_bins))

    # Do linear regression for the N/S position of the line at each longitude.
    for i in range(len(lon_bins)):
        # logger.info(lon_bins[i])
        lat_time_series = lat_northward[i, :]

        slope, intercept, r_value, p_value, std_err = stats.linregress(years, lat_time_series)
        slopes[i] = slope
        intercepts[i] = intercept
        r_values[i] = r_value**2
        p_values[i] = p_value
        std_errs[i] = std_err

    plt.plot(lon_bins, slopes, label='slopes')
    # plt.plot(lon_bins, intercepts, label='intercepts')
    plt.plot(lon_bins, r_values, label='r_values')
    plt.plot(lon_bins, p_values, label='p_values')
    # plt.plot(lon_bins, std_errs, label='std_errs')
    plt.legend()
    plt.show()
    plt.close()


if __name__ == '__main__':
    from SurfaceStressDataWriter import SurfaceStressDataWriter
    from utils import date_range

    # process_and_plot_day(datetime.date(2015, 7, 16))
    # process_day(datetime.date(2015, 7, 16))
    # plot_day(datetime.date(2015, 7, 16))
    # process_day(datetime.date(2015, 1, 1))

    # produce_monthly_mean(datetime.date(2015, 7, 1))
    # produce_monthly_climatology([2, 3, 7, 8, 9], 1992, 2015)

    # produce_seasonal_climatology(['JAS'], 1992, 2015)
    # for year in range(1992, 2016):
    #     produce_seasonal_mean(['JFM'], year)

    # process_multiple_years(1995, 1995)

    # produce_annual_mean(2000)
    # for year in range(1992, 2016):
    #     produce_annual_mean(year)

    # produce_climatology(1992, 2015)

    # process_neutral_density_fields_multiple_depths(time_span='A5B2', avg_period='00', grid_size='04', field_type='an',
    #                                                depth_levels=range(8))
    # process_neutral_density_fields_multiple_depths(time_span='95A4', avg_period='00', grid_size='04', field_type='an',
    #                                                depth_levels=range(8))
    # process_neutral_density_fields_multiple_depths(time_span='A5B2', avg_period='13', grid_size='04', field_type='an',
    #                                                depth_levels=range(8))
    # process_neutral_density_fields_multiple_depths(time_span='A5B2', avg_period='14', grid_size='04', field_type='an',
    #                                                depth_levels=range(8))
    # process_neutral_density_fields_multiple_depths(time_span='A5B2', avg_period='15', grid_size='04', field_type='an',
    #                                                depth_levels=range(8))
    # process_neutral_density_fields_multiple_depths(time_span='A5B2', avg_period='16', grid_size='04', field_type='an',
    #                                                depth_levels=range(8))

    # plot_meridional_salinity_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=-135, split_depth=250)
    # plot_meridional_salinity_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=-30, split_depth=250)
    # plot_meridional_salinity_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=75, split_depth=250)

    # plot_meridional_temperature_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=-135, split_depth=500)
    # plot_meridional_temperature_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=-30, split_depth=500)
    # plot_meridional_temperature_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=75, split_depth=500)
    #
    # dates = []
    # for year in range(2005, 2006):
    #     dates = dates + date_range(datetime.date(year, 7, 1), datetime.date(year, 9, 30))
    #
    # surface_stress_dataset = SurfaceStressDataWriter(None)
    # surface_stress_dataset.date = dates[-1]
    # surface_stress_dataset.compute_mean_fields(dates, avg_method='partial_data_ok')
    # surface_stress_dataset.plot_diagnostic_fields(plot_type='custom', custom_label='2005-2012_JAS')

    # look_at_neutral_density_contours(2005, 2012)
    # look_at_neutral_density_contours(2014, 2015)
    # look_at_neutral_density_contours(1992, 1993)
    #
    # plot_meridional_gamma_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=-135, split_depth=250)
    # plot_meridional_gamma_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=-30, split_depth=250)
    # plot_meridional_gamma_profiles(time_span='A5B2', grid_size='04', field_type='an', lon=75, split_depth=250)

    analyze_zero_zonal_stress_line(custom_str='climo')
