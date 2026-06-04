#!/bin/bash

# Path to Kerchunk reference files
REF_DIR="/glade/u/home/bonnland/scratch/MMLEA_d651039"

# Path to catalog generator 
SRC_DIR="/glade/u/home/bonnland/GitRepos/gdex-intake-esm/generator"

OPTIONS1='--data_format reference --output_format csv_and_json --catalog_name d651039_catalog --depth 0'
OPTIONS2='--use_cftime True --ignore_vars time_bnds'

python $SRC_DIR/create_catalog.py $REF_DIR $OPTIONS1 $OPTIONS2 --description "MMLEA2 kerchunk catalog"

