#!/usr/bin/env python
import sys
import os
import argparse
import re
import pdb
import logging

import xarray
import pandas as pd
import intake_esm
import ecgtools
import fsspec

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(__name__)



NO_DATA_STR = ""

def get_parser():
    """Returns argpars parser."""
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
    parser.add_argument('--catalog_name', '-n',
            type=str,
            required=False,
            metavar='<name>',
            default='catalog',
            help="Name of catalog")
    parser.add_argument('--description',
            type=str,
            required=False,
            metavar='<description>',
            default='N/A',
            help="Description of catalog")
    parser.add_argument('--exclude', '-e',
            nargs='*',
            required=False,
            metavar='<glob>',
            help="Exclude glob")
    parser.add_argument('--depth', '-d',
            type=int,
            nargs=None,
            required=False,
            metavar='<value>',
            default=0,
            help="depth to search")
    parser.add_argument('--ignore_vars', '-i',
            type=str,
            nargs='*',
            required=False,
            metavar='<var name>',
            default=[],
            help="Optionally ignore specific variables e.g. utc_date")
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
    parser.add_argument('--make_remote', '-mr',
            action='store_true',
            required=False,
            help='Additionally make a remote accessible copy of json/csv',
            default=False)

    return parser

def get_engine(file_path):
    """Gets xarray engine based on file.

    Args:
        file_path(str): determines engine based on filepath.

    Returns:
        engine(str): xarray engine string.
    """
    if re.match('.*\.nc$', file_path):
        return 'netcdf4'
    if re.match('.*\.grib$', file_path) or re.match('.*\.grb$', file_path):
        return 'cfgrib'
    if re.match('.*\.zarr$', file_path):
        return 'zarr'
    if re.match('.*\.json$', file_path):
        return 'reference'


def file_parser(file_path, ignore_vars=[], var_metadata=[], global_metadata=[]):
    """File parser used in Builder object to extract column values.

    Args:
        file_path (str, Path): path to data_file
        ignore_vars (list(str)): Variable names to ignore. e.g. 'utc_time'
        var_metadata (list(str): Extra variable level metadata to pull.
                format is [{'<prefered column name>: <variable attr>:<default value>


    Returns:
        dict: Keys are column names and values specific to file.
    """
    print(f'Gathering {file_path}')
    engine = get_engine(file_path)
    rows = []
    backend_kwargs = None
    path_str = file_path
    _format = engine
    if engine == 'netcdf4':
        _format = 'netcdf'
    if engine == 'reference':
            fs = fsspec.filesystem('reference', fo=file_path)
            file_path = fs.get_mapper('')
            engine = 'zarr'
            backend_kwargs = {'consolidated':False}
    with xarray.open_dataset(file_path, engine=engine, backend_kwargs=backend_kwargs) as ds:
        for var_name in ds.data_vars:
            if var_name in ignore_vars:
                continue
            row = {'path':path_str, 'variable':var_name, 'format':_format}
            var = ds[var_name]
            if len(var_metadata) > 0:
                for attr in var_metadata:
                    if attr in var.attrs:
                        row.update({attr:var.attrs[attr]})
            if len(global_metadata) > 0:
                for attr in global_metadata:
                    if attr in ds.attrs:
                        row.update({v:var.attrs[v]})
            row.update(get_var_attrs(var))
            rows.append(row)
    print(f'rows:{len(rows)}')
    return rows

def get_default_var_metadata():
    # Default metadata to check in a variable.
    # The key is the attr name. The value is default value.
    default_var_attrs = {
            'long_name' : {'':''},
            'short_name' : {'':''},
            }
    return default_var_attrs

def get_var_attrs(var):
    """Gets relevant metadata from xarray DataArray-like object.

    Args:
        var (xarray.core.dataarray.DataArray): Variable to pull attributes.

    Returns:
        dict: Contains variable level metadata
    """
    var_attrs = {}
    var_attrs['short_name'] = var.attrs.get('short_name', var.name)
    var_attrs['long_name'] = var.attrs.get('long_name', NO_DATA_STR)
    var_attrs['units'] = var.attrs.get('units', NO_DATA_STR)
    # Get time and level
    var_attrs['start_time'] = ''
    var_attrs['end_time'] = ''
    var_attrs['level'] = ''
    var_attrs['level_units'] = ''
    var_attrs['frequency'] = ''
    for coord in var.coords:
        cur_var = var[coord]
        if 'standard_name' in cur_var.attrs and cur_var.standard_name == 'time' \
                or coord.lower() == 'time':
            time = cur_var.data.flatten()
            var_attrs['start_time'] = time[0]
            var_attrs['end_time'] = time[-1]
            if len(time) > 1:
                var_attrs['frequency'] = time[1] - time[0]
        if 'vertical_orientation' in cur_var.attrs:
            if 'standard_name' in cur_var.attrs:
                var_attrs['level'] = cur_var.attrs['standard_name']
            if 'units' in cur_var.attrs:
                var_attrs['level_units'] = cur_var.attrs['units']
    return var_attrs


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

    logger.debug(f'Parsing args: {args}')
    args_dict = vars(args)
    args_dict.pop('global_metadata')
    args_dict.pop('var_metadata')
    create_catalog(**args_dict)

def make_remote(filename):
    """Make OSDF and HTTP versions of a given file."""
    print(f'Making remote copies of {filename}')

    osdf_outfile = filename.replace('.csv','-osdf.csv')
    https_outfile = filename.replace('.csv','-http.csv')
    with open(filename) as fh:
        osdf_fh = open(osdf_outfile, 'w')
        https_fh = open(https_outfile, 'w')
        for i in fh:
            new_str_osdf = i.replace('/glade/campaign/collections/rda/data/','osdf://data.rda.ucar.edu/')
            osdf_fh.write(new_str_osdf)
            new_str_https = i.replace('/glade/campaign/collections/rda/data/','https://data.rda.ucar.edu/')
            https_fh.write(new_str_https)


def create_catalog(directories, out='./', depth=20, exclude='',
                   catalog_name='catalog', description='', make_remote=False,  **kwargs):
    print(kwargs)
    b = ecgtools.Builder(paths=directories,
                         depth=depth,
                         exclude_patterns=exclude)
    b.build(parsing_func=file_parser, parsing_func_kwargs=kwargs)

    # extract dicts and combine
    new_df = pd.DataFrame(columns=b.df[0][0].keys())
    dict_list = []
    for i,d in b.df.iterrows():
        for j in d:
            if j:
                dict_list.append(j)
    b.df = new_df.from_records(dict_list)

    b.save(
    name=catalog_name,
    path_column_name='path',
    variable_column_name='variable',
    data_format='netcdf',
    format_column_name='format',
    groupby_attrs=[
        'variable',
        'short_name'
    ],
    aggregations=[
        {'type': 'union', 'attribute_name': 'variable'},
        {
            'type': 'join_existing',
            'attribute_name': 'time_range',
            'options': {'dim': 'time', 'coords': 'minimal', 'compat': 'override'},
        },
    ],
    description = description,
    directory = out
    )
    print(kwargs)
    if 'make_remote' in kwargs and kwargs['make_remote']:
        make_remote(os.path.join(out,f'{catalog_name}.csv'))




if __name__ == '__main__':
    main(sys.argv[1:])

