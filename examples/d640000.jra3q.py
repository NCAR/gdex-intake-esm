"""
Catalog the Kerchunk files for the d640000 dataset.

[original github script location]
https://github.com/chiaweh2/gdex_work/blob/main/d640000.jra3q/catalog_kerchunk.py

Make sure the reference files are created and archived before running this script.
- batch_kerchunk.py
- dsarch_kerchunk.py

Main CLI commands:
python create_catalog.py <archived-reference-file-location> --data_format reference --out <output-directory> --output_format csv_and_json --catalog_name dxxxxxx_catalog --description "kerchunk catalog" --depth 0 --make_remote


Notes:
It always create the posix catalog first based on archived reference files,
then use the posix catalog to create the https and osdf catalogs
(so nothing is related to the local created reference files created for the remote data access).
by using the --make_remote option. The two other remote catalogs will have "-https" and "-osdf" suffixes in the filenames.
It will also be archived under the group index -2 along with the posix catalog.

"""

import os
import logging
import subprocess
from gdex_work_utils import load_gdex_work_env, setup_logging

# setup global variable
DATASET_ID = 'd640000'
PARENT_GROUP_INDEX = -2


# Setup logging
log_file = setup_logging(__file__, log_name='catalog_kerchunk.log')

# load environment variables
load_gdex_work_env()

if __name__ == "__main__":
    logging.info("Starting cataloging process...")

    # define paths
    archived_ref_dir = os.path.join(
        os.environ['GLADE_DATA'], f"{DATASET_ID}/kerchunk"
    )
    catalog_cli = os.path.join(
        os.environ['HOME_DIR'], "gdex-intake-esm/generator/create_catalog.py"
    )
    temp_dir = os.path.join(
        os.environ['SCRATCH_DIR'], f"{DATASET_ID}.jra3q/catalog/"
    )

    # find include exclude patterns based on catalog type
    # create only based on the posix
    # the make remote options will create the https and osdf catelog
    # based on posix catalog files
    include_patterns = None
    exclude_patterns = ["*-remote-*"]

    command = (
        f"python {catalog_cli} {archived_ref_dir} "
        "--data_format reference "
        f"--out {temp_dir} "
        f"--include {include_patterns} "
        f"--exclude {' '.join(exclude_patterns)} "
        "--output_format csv_and_json "
        f"--catalog_name {DATASET_ID}_catalog "
        "--description 'JRA3Q kerchunk catalog' "
        "--depth 0 "
        "--make_remote"
    )

    # catalog the archived kerchunk reference files and save to scratch
    logging.info("-------------------------------------")
    logging.info("Cataloging kerchunk reference files in: %s", archived_ref_dir)
    logging.info("Output catalog directory: %s", temp_dir)
    logging.info("Create catalog command: %s", command)
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as err_result:
        logging.error(f"Cataloging command failed with exit code {err_result.returncode}")
        logging.error(f"STDOUT: {err_result.stdout}")
        logging.error(f"STDERR: {err_result.stderr}")
        result = err_result

    if result.returncode == 0:
        logging.info("Cataloging completed with output: \n %s", result.stdout)
        logging.info("Cataloging completed successfully.")
    else:
        logging.error("Cataloging failed with return code: %s", result.returncode)
        logging.error("Cataloging failed with output: \n %s", result.stdout)
        logging.error("Cataloging failed with error: \n %s", result.stderr)
    logging.info("-------------------------------------")