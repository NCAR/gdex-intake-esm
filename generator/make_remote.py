import sys
import os
import argparse

def make_remote(filename, old_path, prefix=None):
    """
    Make OSDF and HTTPS versions of a given CSV file by replacing the old path prefix.
    Outputs two new files:
      - <prefix>-osdf.csv with 'osdf://' prefix
      - <prefix>-https.csv with 'https://' prefix
    
    If prefix is not provided, the input filename is used as the prefix.
    """
    # Determine output filename prefixes
    if prefix:
        osdf_outfile = f"{prefix}-osdf.csv"
        https_outfile = f"{prefix}-https.csv"
    else:
        osdf_outfile = filename.replace('.csv', '-osdf.csv')
        https_outfile = filename.replace('.csv', '-https.csv')
    
    try:
        # Open input and output files
        with open(filename, 'r') as fh, \
             open(osdf_outfile, 'w') as osdf_fh, \
             open(https_outfile, 'w') as https_fh:
            
            # Process each line
            for line in fh:
                # Replace old path with new OSDF path
                new_str_osdf = line.replace(old_path, 'osdf://data.rda.ucar.edu/')
                osdf_fh.write(new_str_osdf)
                
                # Replace old path with new HTTPS path
                new_str_https = line.replace(old_path, 'https://data.rda.ucar.edu/')
                https_fh.write(new_str_https)
        
        print(f"Successfully created:\n  - {osdf_outfile}\n  - {https_outfile}")
    
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Use argparse for better command-line argument handling
    parser = argparse.ArgumentParser(description="Create OSDF and HTTPS versions of a catalog CSV file.")
    parser.add_argument("input_file", help="Input CSV file")
    parser.add_argument("old_path", help="Old path prefix to be replaced")
    parser.add_argument("--prefix", help="Custom prefix for output filenames (optional)")

    args = parser.parse_args()

    # Run the make_remote function with provided arguments
    make_remote(args.input_file, args.old_path, args.prefix)

