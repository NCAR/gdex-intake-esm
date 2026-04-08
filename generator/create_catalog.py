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
    [--include <glob>]
    [--depth <value>]
    [--ignore_vars <var name>]
    [--var_metadata <json string/filename>]
    [--global_metadata <json string/filename>]
    [--output_format <csv_and_json/single_json>]
    [--make_remote]

Notes:
- if --make_remote is set, the catalog naming convention must be followed:
    {dataset_id}-{protocol}

Testing example:
python create_catalog.py /lustre/desc1/scratch/chiaweih/d640000.jra3q/kerchunk_test/ --data_format reference --out /lustre/desc1/scratch/chiaweih/d640000.jra3q/catalog --output_format csv_and_json --catalog_name d640000_catalog --description "JRA3Q kerchunk catalog" --depth 0 --make_remote
python create_catalog.py s3://gdex-data/d010096/AS-RCEC/TaiESM1/1pctCO2/r1i1p1f1/Amon/clivi/gn/ --data_format zarr --catalog_data zarr-boreas --out /lustre/desc1/scratch/chiaweih/d010096.cmip6/catalog --output_format csv_and_json --catalog_name d010096-posix --description "CMIP6 zarr catalog" --depth 0 --make_remote
python create_catalog.py s3://gdex-data/d010096/ --data_format zarr --catalog_data zarr-boreas --out /lustre/desc1/scratch/chiaweih/d010096.cmip6/catalog --output_format csv_and_json --catalog_name d010096-posix --description "CMIP6 zarr catalog" --depth 7  --make_remote

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
from dotenv import load_dotenv

import xarray
import pandas as pd
import ecgtools
import fsspec


# setup logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# constant definitions
NO_DATA_STR = ""

# setup global variables for BOREAS S3 bucket
BOREAS_BUCKET_NAME = 'gdex-data'
BOREAS_ENDPOINT_URL = 'https://boreas.hpc.ucar.edu:6443'

def load_env():
    """
    Load .env file from the top level directory.
        
    Returns
    -------
    bool
        True if .env file was loaded successfully, False otherwise
    """
    # Get the directory where this utils module is located
    utils_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to get to root directory
    root = os.path.dirname(utils_dir)
    env_file = os.path.join(root, '.env')

    log_info = f"Looking for .env file at: {env_file}"
    print(log_info)

    if os.path.exists(env_file):
        success = load_dotenv(env_file)
        if success:
            log_info = f".env file loaded successfully from {env_file}"
            print(log_info)
        else:
            log_error = f"Failed to load .env file from {env_file}"
            print(log_error)
            raise Exception(log_error)
    else:
        log_error = f".env file not found at {env_file}"
        print(log_error)
        raise FileNotFoundError(log_error)

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
    parser.add_argument('--catalog_data', '-cd',
            type=str,
            required=False,
            metavar='<data>',
            choices=['reference', 'zarr-glade', 'zarr-boreas'],
            help='The data format of the catalog (reference / zarr-glade / zarr-boreas).',
            default='reference')
    parser.add_argument('--catalog_name', '-n',
            type=str,
            required=False,
            metavar='<name>',
            default='dnnnnnn-posix',
            help="Name of catalog should be in the format of dnnnnnn-posix to ensure remote copies work.")
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
    parser.add_argument('--include', '-ic',
            nargs='*',
            required=False,
            metavar='<glob>',
            help="Include glob")
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
            nargs='*',
            required=False,
            metavar='<attr name>',
            default=[],
            help="Additional variable level metadata to extract. e.g. long_name standard_name")
    parser.add_argument('--global_metadata', '-gm',
            type=str,
            nargs='*',
            required=False,
            metavar='<attr name>',
            default=[],
            help="Additional global level metadata to extract. e.g. member_id group_id")
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
    parser.add_argument('--use_cftime',
            type=lambda x: x.lower() == 'true',
            metavar='<True|False>',
            required=False,
            help='Use cftime objects for time decoding instead of numpy datetime64.',
            default=False)
   

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

def file_parser(file_path, data_format='netcdf', zarr_format:int=None, ignore_vars=None, var_metadata=None, global_metadata=None, use_cftime=False):
    """File parser used in Builder object to extract column values.

    Args:
        file_path (str, Path): path to data_file
        data_format (str): data format of file. Options: 'netcdf', 'zarr', 'reference'
        zarr_format (int): if data_format is zarr, specify zarr version (2 or 3)
        ignore_vars (list(str)): Variable names to ignore. e.g. 'utc_time'
        var_metadata (list(str)): Extra variable level metadata to pull.
            ex: ['long_name', 'standard_name']
        global_metadata (list(str)): Extra global level metadata to pull.
            ex: ['title', 'institution']
        use_cftime (bool): Whether to use cftime for time decoding.
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
    backend_kwargs = {}

    print(f'Gathering {file_path}')
    path_str = file_path

    # set backend_kwarg for cftime decoding if option is set
    if use_cftime:
        time_coder = xarray.coders.CFDatetimeCoder(use_cftime=True)
        backend_kwargs['decode_times'] = time_coder
        try:
            # test if cftime decoding works for this file
            with xarray.open_dataset(file_path, engine=get_engine(file_path), backend_kwargs=backend_kwargs) as ds:
                pass
        except ValueError as e:
            backend_kwargs['decode_times'] = False
            print(f'Warning: cftime decoding failed for file {file_path} with error: {e}. Falling back to no time decoding.')
    else:
        backend_kwargs['decode_times'] = None

    # Handle reference case
    if data_format == 'reference':
        print(f'Handling reference format for file: {file_path}')
        if version.parse(xarray.__version__) < version.parse('2025.9.1'):
            # original kerchunk handling in xarray
            fs = fsspec.filesystem('reference', fo=file_path)
            file_path = fs.get_mapper('')
            engine = 'zarr'
            backend_kwargs['consolidated'] = False
        else:
            # works for kerchunk or virtualizarr references
            engine = 'kerchunk'
    # Handle zarr case with versioning option
    elif data_format == 'zarr':
        engine = 'zarr'
        if zarr_format is None:
            zarr_format = 2
        print(f'Handling zarr format for file: {file_path} with zarr_format: {zarr_format}')
        backend_kwargs['consolidated'] = True
        backend_kwargs['zarr_format'] = int(zarr_format)
        
        # change to https:// boreas internal end point if file_path is s3://
        if re.match('s3://.*', file_path):
            file_path = file_path.replace(
                f's3://{BOREAS_BUCKET_NAME}/',
                f'{BOREAS_ENDPOINT_URL}/{BOREAS_BUCKET_NAME}/'
            )
            path_str = file_path
    else:
        print(f'Handling netcdf/grib format for file: {file_path}')
        engine = get_engine(file_path)

    # if empty reset to None for xarray compatibility
    if backend_kwargs == {}:
        backend_kwargs = None
        

    # try:
    #     xarray.open_dataset(file_path, engine=engine, backend_kwargs=backend_kwargs)
    # except Exception:
    #     if data_format == 'zarr':
    #         return catalog_items
    #     raise


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
                    # if attr in ds.attrs:
                    globalmeta= ds.attrs.get(attr, NO_DATA_STR)
                    catalog_item.update({attr:globalmeta})

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


def make_remote_catalog(filename, catalog_data='reference', output_format='csv_and_json'):
    """
    Make OSDF and HTTP versions of a given file.

    Parameters
    ----------
    filename : str
        Local file path to the catalog file (csv or json).
    catalog_data : str
        The type of data to be cataloged, which determines how paths are modified.
        Options are 'reference', 'zarr-boreas', and 'zarr-glade'. Default is 'reference'.
    output_format : str
        The format of the catalog file, which determines how the file is read and modified.
        Options are 'csv_and_json' and 'single_json'. Default is 'csv_and_json'.
        
    Raises
    ------
    ValueError
        If the filename does not follow the required naming convention
        of {dataset_id}-posix{.csv/.json}.

    Notes
    -----
    Assumes that the input filename contains paths. Both the OSDF and HTTP
    versions will be created by replacing the local path prefix with the
    appropriate remote path prefix. The posix protocol file name must be in
    the format of 

        {dataset_id}-{protocol}.csv or .json

    Since the catalog file name is not foreced to be in that format,
    The function will check for the filenaming convention to determine
    if the file is valid for remote copy creation. if convention is not 
    met, an error will be raised and the function will exit.

    """
    print(f'Making remote copies of {filename}')
    # find name before extension
    filename_base = os.path.basename(filename)
    # find output directory path
    out_dir = os.path.dirname(filename)
    # based on catalog output format get the dataset number
    dataset_id = filename_base.split('-')[0]

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
    osdf_outfile = filename.replace(f'-posix{output_ext}', f'-osdf{output_ext}')
    https_outfile = filename.replace(f'-posix{output_ext}', f'-https{output_ext}')
    # check if catalog filename follows naming convention
    if osdf_outfile == filename or https_outfile == filename:
        raise ValueError(
            f'Filename {filename} does not follow the required naming convention of {{dataset_id}}-posix{{.csv/.json}}'
        )

    # define replacement strings and write new files
    if catalog_data == 'reference':
        match_str = '/glade/campaign/collections/gdex/data/'
        https_str = 'https://data.gdex.ucar.edu/'
        # osdf_str = 'https://data-osdf.gdex.ucar.edu/'
        # osdf_str = 'osdf:///ncar/gdex/'
        # read reference file from globus end point
        osdf_str = https_str
    elif catalog_data == 'zarr-boreas':
        match_str = f'{BOREAS_ENDPOINT_URL}/{BOREAS_BUCKET_NAME}/'
        https_str = 'https://osdata.gdex.ucar.edu/'
        osdf_str = 'osdf:///ncar-gdex/'
        # osdf_str = 'https://osdf-director.osg-htc.org/ncar-gdex/'
    elif catalog_data == 'zarr-glade':
        match_str = '/glade/campaign/collections/gdex/data/'
        https_str = 'https://data.gdex.ucar.edu/'
        osdf_str = 'osdf:///ncar/gdex/'
        # osdf_str = 'https://osdf-director.osg-htc.org/ncar/gdex/'
    else:
        raise ValueError(f'Unsupported catalog data type: {catalog_data}')


    if output_format.lower() == 'csv_and_json' :
        # modify csv file line by line
        with open(filename, 'r', encoding='utf-8') as fh:
            osdf_fh = open(osdf_outfile, 'w', encoding='utf-8')
            https_fh = open(https_outfile, 'w', encoding='utf-8')
            for i in fh:
                if i.split(',')[0].strip() == 'path':
                    # write header line
                    osdf_fh.write(i)
                    https_fh.write(i)
                    continue
                # seperate each line by comma (assuming path is the first column)
                url_https = i.split(',')[0]
                # change the path (https protocol)
                url_https = url_https.replace(match_str, https_str)
                if catalog_data == 'reference':
                    # change the basename to include protocol
                    basename_https = os.path.basename(url_https)
                    rename_basename_elem_https = basename_https.split('.')
                    rename_basename_elem_https[-2] = rename_basename_elem_https[-2] + '-remote-https'
                    rename_basename_https = '.'.join(rename_basename_elem_https)
                    url_https = url_https.replace(basename_https, rename_basename_https)
                # replace path in line
                https_new_line = i.replace(i.split(',')[0], url_https)
                # write new line
                https_fh.write(https_new_line)

                # seperate each line by comma (assuming path is the first column)
                url_osdf = i.split(',')[0]
                # change the path (osdf protocol)
                url_osdf = url_osdf.replace(match_str, osdf_str)
                if catalog_data == 'reference':
                    # change the basename to include protocol
                    basename_osdf = os.path.basename(url_osdf)
                    rename_basename_elem_osdf = basename_osdf.split('.')
                    rename_basename_elem_osdf[-2] = rename_basename_elem_osdf[-2] + '-remote-osdf'
                    rename_basename_osdf = '.'.join(rename_basename_elem_osdf)
                    url_osdf = url_osdf.replace(basename_osdf, rename_basename_osdf)
                # replace path in line
                osdf_new_line = i.replace(i.split(',')[0], url_osdf)
                # write new line
                osdf_fh.write(osdf_new_line)

            osdf_fh.close()
            https_fh.close()

        # modify json file that is associated with csv
        json_filename = os.path.join(out_dir, filename_base.replace('.csv', '.json'))
        with open(json_filename) as fh:
            data = json.load(fh)
        # Create OSDF version dir structure need to be
        #  https://data-osdf.gdex.ucar.edu/{dataset_id}/catalogs/{dataset_id}-osdf.csv
        # data['catalog_file'] = f'{osdf_str}{dataset_id}/catalogs/{dataset_id}-osdf.csv'
        data['catalog_file'] = f'{dataset_id}-osdf.csv'
        osdf_outfile = json_filename.replace('-posix.json', '-osdf.json')
        with open(osdf_outfile, 'w') as osdf_fh:
            json.dump(data, osdf_fh)
        # Create HTTPS version
        #  https version dir structure need to be
        #  https://data.gdex.ucar.edu/{dataset_id}/catalogs/{dataset_id}-https.csv
        # data['catalog_file'] = f'{https_str}{dataset_id}/catalogs/{dataset_id}-https.csv'
        data['catalog_file'] = f'{dataset_id}-https.csv'
        https_outfile = json_filename.replace('-posix.json', '-https.json')
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
        with open(osdf_outfile, 'w') as osdf_fh:
            json.dump(data_osdf, osdf_fh)
        # Create HTTPS version
        data_https = json.loads(json.dumps(data).replace(match_str, https_str))
        with open(https_outfile, 'w') as https_fh:
            json.dump(data_https, https_fh)

    else:
        raise ValueError(f'Unsupported output format: {output_format}')


def create_catalog(
    directories,
    storage_options=None,
    out='./',
    depth=20,
    include=None,
    exclude=None,
    catalog_data='reference',
    catalog_name=None,
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
        include: Regex to include. e.g. .*\.nc
        exclude: Regex to exclude. e.g. .*\.html
        catalog_name (str): filename of catalog
        description (str): short description of catalog.
        make_remote (bool): make OSDF and HTTP versions of this dataset
        kwargs: Aditional parsing function arguments
    """
    print(kwargs)

    for directory in directories:
        if 's3://' in directory and not storage_options:
            raise ValueError(f"Directory {directory} is an s3 path but no storage options were provided.")

    b = ecgtools.Builder(
        paths=directories,
        depth=depth,
        include_patterns=include,
        exclude_patterns=exclude,
        storage_options=storage_options
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
        data_format=kwargs['data_format'],
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
        make_remote_catalog(remote_catalog_file, catalog_data=catalog_data, output_format=output_format)


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

    # Auto-populate storage_options when any directory is an s3:// path
    if any(d.startswith('s3://') for d in args_dict['directories']):
        print('S3 path detected in directories, auto-populating storage_options for BOREAS S3 bucket.')
        # load BOREAS credentials from .env file in top level directory
        load_env()
        BOREAS_ACCESS_KEY_ID = os.getenv('BOREAS_ACCESS_KEY_ID')
        BOREAS_SECRET_ACCESS_KEY = os.getenv('BOREAS_SECRET_ACCESS_KEY')
        args_dict['storage_options'] = {
            's3': {
                'client_kwargs': {'endpoint_url': BOREAS_ENDPOINT_URL},
                'key': BOREAS_ACCESS_KEY_ID,
                'secret': BOREAS_SECRET_ACCESS_KEY
            }
        }

    # remove unneeded args (for consistency with other dataset)
    # args_dict.pop('global_metadata')
    # args_dict.pop('var_metadata')
    # call create_catalog with args
    # print(f'Creating catalog with args: {args_dict}')
    create_catalog(**args_dict)


if __name__ == '__main__':
    main(sys.argv[1:])
