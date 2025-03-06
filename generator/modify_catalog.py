import argparse

def modify_catalog(input_file, output_file, old_path, new_path):
    """
    Reads an input file, replaces the specified old path with the new path, and writes to an output file.

    Parameters:
    - input_file (str): Path to the input file.
    - output_file (str): Path to the output file.
    - old_path (str): The path to be replaced.
    - new_path (str): The replacement path.

    Outputs:
    - A single modified file with all occurrences of old_path replaced by new_path.
    """
    try:
        with open(input_file, 'r') as fh, open(output_file, 'w') as out_fh:
            for line in fh:
                new_line = line.replace(old_path, new_path)
                out_fh.write(new_line)

        print(f"Successfully created: {output_file}")

    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replace paths in a file and save the modified version.")
    parser.add_argument("input_file", help="Input file to process")
    parser.add_argument("output_file", help="Output file to save the modified content")
    parser.add_argument("old_path", help="The old path to be replaced")
    parser.add_argument("new_path", help="The new path to replace with")

    args = parser.parse_args()

    # Run the modify_catalog function
    modify_catalog(args.input_file, args.output_file, args.old_path, args.new_path)

