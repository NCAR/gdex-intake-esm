#!/usr/bin/env python
import sys
import os
import argparse
import re
import pdb

import intake_esm
import ecgtools


# Default metadata to check in a variable.
# The key is the attr name. The value is default value.
default_var_attrs = {
        'long_name' : '',
        'short_name' : ''
        }

def get_parser():
    description = "CLI to generate intake-esm cataloges."
    parser = argparse.ArgumentParser(
            prog='create_catalog',
            description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter)

    # Arguments that are always allowed
    parser.add_argument('directories',
            nargs='+',
            metavar='<directory>',
            help="Directory or directories to scan.")
    parser.add_argument('--out', '-o',
            type=str,
            required=False,
            metavar='<directory>',
            default='./',
            help="Directory to ouput json and csv.")
    parser.add_argument('--exclude', '-e',
            nargs='*',
            required=False,
            metavar='<glob>',
            help="Exclude glob")
    parser.add_argument('--depth', '-d',
            type=int,
            nargs='*',
            required=False,
            metavar='<value>',
            default=0,
            help="depth to search")
    parser.add_argument('--depth', '-d',
            type=int,
            nargs='*',
            required=False,
            metavar='<value>',
            default=0,
            help="depth to search")
    parser.add_argument('--var_metadata', '-vm',
            type=str,
            required=False,
            metavar='<json string/filename>',
            default='{}',
            help="Additional variable level metadata to extract.")
    parser.add_argument('--global_metadata', '-gm',
            type=str,
            required=False,
            metavar='<json string/filename>',
            default='{}',
            help="Additional global level metadata to extract.")

    return parser

def get_engine(file_path):
    """Gets xarray engine based on file."""
    #TODO: what if kerchunk reference?
    if re.match('.*\.nc$', file_path):
        return 'netcdf'
    if re.match('.*\.grib$', file_path) or re.match('.*\.grb$', file_path):
        return 'cfgrib'
    if re.match('.*\.zarr$', file_path):
        return 'zarr'

def file_parser(file_path, ignore_vars=[]):
    """File parser used in Builder object to extract column values.

    Args:
        file_path (str, Path): path to data_file
        ignore_vars (list[str]): Variable names to ignore. e.g. 'utc_time'

    Returns:
        dict: Keys are column names and values specific to file.
    """
    engine = get_engine(file_path)
    with xr.open_dataset(file_path, engine=engine) as ds:
        for var_name in ds.data_vars:
            var = ds[var_name]
            short_name = var.attrs.get('short_name', var_name)
            long_name = var.attrs.get('long_name', '')
            units = var.attrs.get('units', '')

    return details


def main(args_list):
    """Use command line-like arguments to execute

    Args:
        args_list (unpacked list): list of args as they would be passed to command line.

    Returns:
        (dict, generally) : result of argument call.
    """
    parser = get_parser()
    if len(args_list) == 0:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args(args_list)
    print(args)


def create_catalog(directories, out_dir='./'):
    b = Builder(paths=[era5_path+'e5.oper.an.vinteg/194001'],depth=0,exclude_patterns=['*.grb'])
    b.build(parsing_func= parse_era5)
    b.save(
    name='era5_catalog_test',
    path_column_name='path',
    variable_column_name='variable',
    data_format='netcdf',
    groupby_attrs=[
        'datatype',
        'level_type',
        'step_type'
    ],
    aggregations=[
        {'type': 'union', 'attribute_name': 'variable'},
        {
            'type': 'join_existing',
            'attribute_name': 'time_range',
            'options': {'dim': 'time', 'coords': 'minimal', 'compat': 'override'},
        },
    ],
    description = 'This is the NetCDF collection of vertical integrals in the ERA5 dataset ds633, which is a part of NCAR glade collection. ',
    directory = '/gpfs/csfs1/collections/rda/scratch/harshah/intake_catalogs/'
    )


if __name__ == '__main__':
    main(sys.argv[1:])

