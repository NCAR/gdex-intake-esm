#!/usr/bin/env python
"""CLI to generate intake-esm cataloges.
Can handle zarr, kerchunk, netcdf, or grib.

Package version needed to be pined:
    intake-esm==2025.7.9
    pydantic==2.11.9
    ecgtools@git+https://github.com/rpconroy/ecgtools.git@0b3d5b5d0082812e85c821c00c2d619eed0ae3cd#egg=ecgtools

Usage:    

python create_catalog.py <directory> 
          [--out <output directory>]
          [--catalog_name <name>]
          [--description <description>]
          [--exclude <glob>]
          [--depth <value>]
          [--ignore_vars <var name>]
          [--var_metadata <json string/filename>]
          [--global_metadata <json string/filename>]
          [--output_format <csv_and_json/single_json>]
          [--make_remote]


Testing example:
python create_catalog.py /lustre/desc1/scratch/chiaweih/d640000.jra3q/kerchunk_test/ --data_format reference --out /lustre/desc1/scratch/chiaweih/d640000.jra3q/catalog --output_format csv_and_json --catalog_name d640000_catalog --description "JRA3Q kerchunk catalog" --depth 0 --make_remote
"""
# import pdb
# import intake_esm
import sys
import os
import re
import json
import logging
import argparse
from packaging import version

import xarray
import pandas as pd
import ecgtools
import fsspec


# setup logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# constant definitions
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
    parser.add_argument('--data_format', '-df',
            type=str,
            required=False,
            metavar='<format>',
            choices=['netcdf', 'zarr', 'reference'],
            help='The data format of the catalog (netcdf / zarr / reference).',
            default='netcdf')
    parser.add_argument('--out', '-o',
            type=str,
            required=False,
            metavar='<directory>',
            default='./',
            help="Directory to ouput catalog file.")
    parser.add_argument('--catalog_name', '-n',
            type=str,
            required=False,
            metavar='<name>',
            default='intake_catalog',
            help="Name of catalog should be in the format of dxxxxxx_catalog")
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
    parser.add_argument('--output_format', '-of',
            type=str,
            required=False,
            metavar='<format>',
            choices=['csv_and_json', 'single_json'],
            help='The output format of the catalog (csv_and_json / single_json).',
            default='csv_and_json')

    return parser

def get_engine(file_path):
    """Get xarray engine based on file extension.

    Args:
        file_path(str): determines engine based on filepath.

    Returns:
        engine(str): xarray engine string.
    """
    if re.match('.*\.nc$', file_path):
        return 'netcdf'
    elif re.match('.*\.grib$', file_path) or re.match('.*\.grb$', file_path):
        return 'cfgrib'
    elif re.match('.*\.zarr$', file_path):
        return 'zarr'
    elif re.match('.*\.json$', file_path):
        return 'reference'
    elif re.match('.*\.parq$', file_path):
        return 'reference'
    else:
        raise ValueError(f'Cannot determine engine for file: {file_path}')

def get_var_attrs(var):
    """Gets relevant metadata from xarray DataArray-like object.

    Args:
        var (xarray.core.dataarray.DataArray): Variable from which to pull attributes.

    Returns:
        dict: Contains variable level metadata
    """
    var_attrs = {}
    var_attrs['short_name'] = var.attrs.get('short_name', var.name)
    var_attrs['long_name'] = var.attrs.get('long_name', NO_DATA_STR)
    if var_attrs['long_name'] == NO_DATA_STR:
        var_attrs['long_name'] = var.attrs.get('description', NO_DATA_STR)
    var_attrs['units'] = var.attrs.get('units', NO_DATA_STR)
    
    # Initialize time and level
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


def file_parser(file_path, data_format='netcdf', ignore_vars=None, var_metadata=None, global_metadata=None):
    """File parser used in Builder object to extract column values.

    Args:
        file_path (str, Path): path to data_file
        ignore_vars (list(str)): Variable names to ignore. e.g. 'utc_time'
        var_metadata (list(str)): Extra variable level metadata to pull.
            ex: ['long_name', 'standard_name']
        global_metadata (list(str)): Extra global level metadata to pull.
            ex: ['title', 'institution']

    Returns:
        dict: Keys are column names and values specific to file.
    """
    # initialize (avoid mutable default arguments)
    if ignore_vars is None:
        ignore_vars = []
    if var_metadata is None:
        var_metadata = []
    if global_metadata is None:
        global_metadata = []

    catalog_items = []
    backend_kwargs = None

    print(f'Gathering {file_path}')
    engine = get_engine(file_path)
    path_str = file_path

    # Handle reference case
    if data_format == 'reference':
        if version.parse(xarray.__version__) < version.parse('2025.9.1'):
            # original kerchunk handling in xarray
            fs = fsspec.filesystem('reference', fo=file_path)
            file_path = fs.get_mapper('')
            engine = 'zarr'
            backend_kwargs = {'consolidated':False}
        else:
            # works for kerchunk or virtualizarr references
            engine = 'kerchunk'


    with xarray.open_dataset(file_path, engine=engine, backend_kwargs=backend_kwargs) as ds:
        for var_name in ds.data_vars:
            # skip ignored variables
            if var_name in ignore_vars:
                continue

            # create basic catalog item
            # catalog_item = {'path':path_str, 'variable':var_name, 'format':data_format} # version before 2024.7.31
            catalog_item = {'path':path_str, 'variable':var_name, 'format':data_format}
            var = ds[var_name]

            # add extra metadata(catalog columns) and its value for each variable
            if len(var_metadata) > 0:
                for attr in var_metadata:
                    if attr in var.attrs:
                        catalog_item.update({attr:var.attrs[attr]})

            # add extra global metadata(catalog columns) and its value for each variable
            if len(global_metadata) > 0:
                for attr in global_metadata:
                    if attr in ds.attrs:
                        catalog_item.update({attr:ds.attrs[attr]})

            # add standard variable attributes
            catalog_item.update(get_var_attrs(var))
            catalog_items.append(catalog_item)

    print(f'Number of catalog_items:{len(catalog_items)}')

    return catalog_items

# def get_default_var_metadata():
#     # Default metadata to check in a variable.
#     # The key is the attr name. The value is default value.
#     default_var_attrs = {
#             'long_name' : {'':''},
#             'short_name' : {'':''},
#             }
#     return default_var_attrs



def convert_to_parquet(filename_base):
    """Convert json and csv file to parquet

    Args:
        filename_base (str): Full filepath--without '.csv' or '.json'

    Returns:
        None
    """
    # json_file = f'{filename_base}.json'
    csv_file = f'{filename_base}.csv'
    parquet_file= f'{filename_base}.parquet'

    df = pd.read_csv(csv_file)
    df.to_parquet(parquet_file)

# def change_catalog_file(json_file, new_catalog_filename):
#     """Change catalog in intake-esm catalog

#     Args:
#         json_file (str): intake-esm catalog filepath
#         new_catalog_filename (str): catalog csv or parquet filename

#     Returns:
#         None
#     """
#     cat = json.load(open(json_file))
#     cat['catalog_file'] = os.path.basename(new_catalog_filename)
#     json.dump(cat, open(json_file, 'w'))


def make_remote_catalog(filename, output_format='csv_and_json'):
    """Make OSDF and HTTP versions of a given file."""
    print(f'Making remote copies of {filename}')
    # find name before extension
    filename_base = os.path.basename(filename)
    # find output directory path
    out_dir = os.path.dirname(filename)
    # based on catalog output format get the dataset number
    dataset_id = filename_base.split('_')[0]

    # check output format
    if output_format.lower() == 'csv_and_json':
        output_ext = '.csv'
    # elif output_format.lower() == 'parquet':
    #     output_ext = '.parq'
    elif output_format.lower() == 'single_json':
        output_ext = '.json'
    else:
        raise ValueError(f'Unsupported output format: {output_format}')

    # define output filenames
    osdf_outfile = filename.replace(output_ext, f'-osdf{output_ext}')
    https_outfile = filename.replace(output_ext, f'-http{output_ext}')

    # define replacement strings and write new files
    match_str = '/glade/campaign/collections/gdex/data/'
    https_str = 'https://data.gdex.ucar.edu/'
    osdf_str = 'https://data-osdf.gdex.ucar.edu/'

    if output_format.lower() == 'csv_and_json':
        # modify csv file line by line
        with open(filename) as fh:
            osdf_fh = open(osdf_outfile, 'w')
            https_fh = open(https_outfile, 'w')
            for i in fh:
                new_str_osdf = i.replace(match_str, osdf_str)
                osdf_fh.write(new_str_osdf)
                new_str_https = i.replace(match_str, https_str)
                https_fh.write(new_str_https)
            osdf_fh.close()
            https_fh.close()

        # modify json file that is associated with csv
        json_filename = os.path.join(out_dir, filename_base.replace('.csv', '.json'))
        with open(json_filename) as fh:
            data = json.load(fh)
        # Create OSDF version dir structure need to be
        #  https://data-osdf.gdex.ucar.edu/{dataset_id}/catalogs/{dataset_id}_catalog-osdf.csv
        data['catalog_file'] = f'{osdf_str}{dataset_id}/catalogs/{dataset_id}_catalog-osdf.csv'
        osdf_outfile = json_filename.replace('.json', '-osdf.json')
        with open(osdf_outfile, 'w') as osdf_fh:
            json.dump(data, osdf_fh)
        # Create HTTPS version
        #  https version dir structure need to be
        #  https://data.gdex.ucar.edu/{dataset_id}/catalogs/{dataset_id}_catalog-http.csv
        data['catalog_file'] = f'{https_str}{dataset_id}/catalogs/{dataset_id}_catalog-http.csv'
        https_outfile = json_filename.replace('.json', '-http.json')
        with open(https_outfile, 'w') as https_fh:
            json.dump(data, https_fh)

    # elif output_format.lower() == 'parquet':
    #     df = pd.read_parquet(filename)
    #     df_osdf = df.copy(deep=True)
    #     df_https = df.copy(deep=True)
    #     df_osdf['path'] = df_osdf['path'].str.replace(match_str, osdf_str)
    #     df_https['path'] = df_https['path'].str.replace(match_str, https_str)
    #     df_osdf.to_parquet(osdf_outfile)
    #     df_https.to_parquet(https_outfile)

    elif output_format.lower() == 'single_json':
        with open(filename) as fh:
            data = json.load(fh)
        # Create OSDF version
        data_osdf = json.loads(json.dumps(data).replace(match_str, osdf_str))
        osdf_outfile = filename.replace(output_ext, f'-osdf{output_ext}')
        with open(osdf_outfile, 'w') as osdf_fh:
            json.dump(data_osdf, osdf_fh)
        # Create HTTPS version
        data_https = json.loads(json.dumps(data).replace(match_str, https_str))
        https_outfile = filename.replace(output_ext, f'-http{output_ext}')
        with open(https_outfile, 'w') as https_fh:
            json.dump(data_https, https_fh)

    else:
        raise ValueError(f'Unsupported output format: {output_format}')


def create_catalog(
    directories,
    out='./',
    depth=20,
    exclude='',
    catalog_name='intake_catalog',
    description='',
    make_remote=False,
    output_format='csv_and_json',
    **kwargs
):
    """Creates an intake esm catalog from a collection assets.
    Can be zarr, kerchunk, netcdf, or grib.
    Args:
        directories (list): Search directories
        out (str): output file location
        depth (int): How deep to search
        exclude: Regex to exclude. e.g. .*\.html
        catalog_name (str): filename of catalog
        description (str): short description of catalog.
        make_remote (bool): make OSDF and HTTP versions of this dataset
        kwargs: Aditional parsing function arguments
    """
    print(kwargs)


    b = ecgtools.Builder(
        paths=directories,
        depth=depth,
        exclude_patterns=exclude
    )
    b.build(parsing_func=file_parser, parsing_func_kwargs=kwargs)


    # extract individual variables dicts and combine
    new_df = pd.DataFrame(columns=b.df[0][0].keys())
    dict_list = []
    for i,d in b.df.iterrows():
        for j in d:
            if j:
                dict_list.append(j)
    b.df = new_df.from_records(dict_list)
    # print(b.df)


    if output_format.lower() == 'csv_and_json':
        catalog_type = 'file'
    elif output_format.lower() == 'single_json':
        catalog_type = 'dict'
    else:
        raise ValueError(f'Unsupported output format: {output_format}')

    # local ecgtools install from the https://github.com/rpconroy/ecgtools
    b.save(
        name=catalog_name,
        path_column_name='path',
        variable_column_name='variable',
        format_column_name='format',
        data_format='reference',
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
        catalog_type=catalog_type,
        description=description,
        directory=out
    )


    
    # if output_format == 'parquet':
    #     convert_to_parquet(os.path.join(out,f'{catalog_name}'))


    # check output format
    if output_format.lower() == 'csv_and_json':
        file_ext = 'csv'
    # elif output_format.lower() == 'parquet':
    #     output_ext = '.parq'
    elif output_format.lower() == 'single_json':
        file_ext = 'json'
    else:
        raise ValueError(f'Unsupported output format: {output_format}')
    
    # change the json file catalog_file entry
    if output_format.lower() == 'csv_and_json':
        # modify json file
        jsonfile = os.path.join(out, f"{catalog_name}.json")
        with open(jsonfile) as fh:
            data = json.load(fh)
        data['catalog_file'] = f'{catalog_name}.csv'
        with open(jsonfile, 'w') as fh:
            json.dump(data, fh)

    if make_remote:
        remote_catalog_file = os.path.join(out,f'{catalog_name}.{file_ext}')
        make_remote_catalog(remote_catalog_file, output_format=output_format)


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

    log_info = f'Parsing args: {args}'
    logger.info(log_info)

    # convert args to dict
    args_dict = vars(args)
    # remove unneeded args (for consistency with other dataset)
    args_dict.pop('global_metadata')
    args_dict.pop('var_metadata')
    # call create_catalog with args
    create_catalog(**args_dict)


if __name__ == '__main__':
    main(sys.argv[1:])

