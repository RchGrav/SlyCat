#!/usr/bin/env python3

import os
import re
import argparse
import fnmatch

# Dictionary mapping file extensions to corresponding code fence languages
CODE_FENCE_LOOKUP = {
    ".py": "python",
    ".js": "javascript",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
    ".java": "java",
    ".cpp": "c++",
    ".c": "c",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".xml": "xml",
    ".rb": "ruby",
    ".rs": "rust",
    ".go": "go",
    ".md": "md",
}

def handle_error(error_message):
    """
    Prints an error message and exits the program.

    Args:
        error_message (str): The error message to display.

    Returns:
        None
    """
    print(f"Error: {error_message}")
    exit(1) 

def is_text_file(file_path):
    """
    Checks if a file is likely a text file based on its content.

    This function attempts to read the first few bytes of the file and checks
    for the presence of null bytes or control characters, which are typically 
    found in binary files. It also excludes files with certain extensions that
    are known to be binary.

    Args:
        file_path (str): Path to the file.

    Returns:
        bool: True if it's likely a text file, False otherwise.
    """
    # Exclude files based on known binary extensions
    binary_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',  # Images
        '.mp3', '.wav', '.ogg', '.flac',  # Audio
        '.mp4', '.avi', '.mov', '.mkv',  # Video
        '.zip', '.rar', '.7z', '.tar', '.gz',  # Archives
        '.exe', '.dll', '.so', '.o', '.pyc', # Executables and object files
        # Add more as needed
    }
    _, ext = os.path.splitext(file_path)
    if ext.lower() in binary_extensions:
        return False

    # Check for null bytes and control characters
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)  # Read a small portion of the file
            if b'\x00' in chunk or any(c < 32 for c in chunk if c != 9 and c != 10 and c != 13):
                return False  # Likely binary
            else:
                return True  # Likely text
    except Exception:  # Handle potential errors (e.g., file not found)
        return False

def write_file_to_output(file_path, base_folder, output_file):
    """
    Writes the content of a file to the output file with markdown code fences.

    Args:
        file_path (str): Path to the file.
        base_folder (str): Base folder for relative path calculation.
        output_file (file object): Output file object.

    Returns:
        None
    """
    # Calculate the relative path including the base_folder name
    rel_path = os.path.relpath(file_path, base_folder)
    base_folder_name = os.path.basename(base_folder.rstrip(os.sep))
    if base_folder_name:
        rel_path = os.path.join(base_folder_name, rel_path)
    else:
        rel_path = os.path.normpath(rel_path)
    _, ext = os.path.splitext(file_path)
    language = CODE_FENCE_LOOKUP.get(ext, "")

    # Attempt to read the file with different encodings
    encodings_to_try = ['utf-8', 'ascii', 'latin-1']
    content = None
    for encoding in encodings_to_try:
        if encoding is None:
            continue
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            break  # Stop trying encodings once successful
        except UnicodeDecodeError:
            continue

    if content is None:
        handle_error(f"Unable to read {file_path} with any of the attempted encodings.")

    output_file.write(f"\n### **`{rel_path}`**\n\n`{language}\n{content}\n`\n")

def should_include(name, includes):
    """
    Checks if a name should be included based on the provided include patterns.

    Args:
        name (str): Name to check (basename of file or directory).
        includes (list): List of include patterns.

    Returns:
        bool: True if the name should be included, False otherwise.
    """
    if not includes:
        return True  # Include all if no patterns are specified
    for pattern in includes:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False

def should_exclude(name, exclusions):
    """
    Checks if a name should be excluded based on the provided exclusion patterns.

    Args:
        name (str): Name to check (basename of file or directory).
        exclusions (list): List of exclusion patterns.

    Returns:
        bool: True if the name should be excluded, False otherwise.
    """
    for pattern in exclusions:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False

def traverse_and_concatenate(current_path, base_folder, output_file, exclusions, includes, processed_files, included_explicitly=False):
    """
    Recursively traverses directories and writes files to the output file.

    Args:
        current_path (str): Current directory or file to process.
        base_folder (str): Base folder for relative path calculation.
        output_file (file object): Output file object.
        exclusions (list): List of exclusion patterns.
        includes (list): List of inclusion patterns.
        processed_files (list): List to store processed file paths.
        included_explicitly (bool): Whether the current directory was included explicitly.

    Returns:
        None
    """
    name = os.path.basename(current_path)

    # Apply inclusion patterns first
    include_current = included_explicitly or should_include(name, includes)

    # Apply exclusion patterns after inclusion
    if should_exclude(name, exclusions):
        return

    if os.path.isdir(current_path):
        # If the directory is included explicitly, include all contents
        if include_current:
            for item in sorted(os.listdir(current_path)):
                item_path = os.path.join(current_path, item)
                traverse_and_concatenate(item_path, base_folder, output_file, exclusions, includes, processed_files, included_explicitly=True)
        else:
            # Continue traversing but apply include patterns at this level
            for item in sorted(os.listdir(current_path)):
                item_path = os.path.join(current_path, item)
                traverse_and_concatenate(item_path, base_folder, output_file, exclusions, includes, processed_files, included_explicitly=False)
    elif os.path.isfile(current_path):
        if include_current:
            if is_text_file(current_path):
                rel_path = os.path.relpath(current_path, base_folder)
                base_folder_name = os.path.basename(base_folder.rstrip(os.sep))
                if base_folder_name:
                    rel_path = os.path.join(base_folder_name, rel_path)
                else:
                    rel_path = os.path.normpath(rel_path)
                print(f"  Adding: {rel_path}")
                processed_files.append(current_path)
                write_file_to_output(current_path, base_folder, output_file)
            else:
                print(f"  Skipped non-text file: {current_path}")
        else:
            # File does not match include patterns and is not in an explicitly included directory
            return

def concatenate_files_and_folders(output_name, paths, force=False, exclusions=[], includes=[]):
    """
    Concatenates text files and folders into a single output file with markdown code fences.

    Args:
        output_name (str): Name of the output file.
        paths (list): List of file and folder paths to concatenate.
        force (bool): Overwrite the output file if it exists.
        exclusions (list): List of exclusion patterns.
        includes (list): List of inclusion patterns.

    Returns:
        None
    """
    if os.path.exists(output_name) and not force:
        handle_error(f"Output file '{output_name}' already exists. Use -f or --force to overwrite.")

    processed_files = []  # Initialize list to store processed files
    skipped_files = []    # Initialize list to store skipped non-text files
    excluded_paths = []   # Initialize list to store excluded paths

    with open(output_name, 'w', encoding='utf-8') as output_file:
        for path in paths:
            if not os.path.exists(path):
                print(f"Warning: '{path}' does not exist, skipping.")
                continue

            name = os.path.basename(path)

            # Apply inclusion patterns first
            include_current = should_include(name, includes) or not includes

            # Apply exclusion patterns after inclusion
            if should_exclude(name, exclusions):
                excluded_paths.append(path)
                continue

            if os.path.isfile(path):
                # Files specified on command line are included explicitly
                if is_text_file(path):
                    # Adjust rel_path to include base folder name
                    rel_path = os.path.basename(path)
                    print(f"  Adding: {rel_path}")
                    processed_files.append(path)
                    write_file_to_output(path, os.path.dirname(path), output_file)
                else:
                    skipped_files.append(path)
            elif os.path.isdir(path):
                # Directories specified on command line are included explicitly
                traverse_and_concatenate(path, os.path.dirname(path), output_file, exclusions, includes, processed_files, included_explicitly=True)
            else:
                print(f"Warning: '{path}' is neither a file nor a folder, skipping.")

    print("\nConcatenation complete.")
    print("\nSummary:")
    print(f"  Output file: {output_name}")  # Print the output file name here
    print(f"  Processed files: {len(processed_files)}")
    if skipped_files:
        print(f"  Skipped non-text files: {len(skipped_files)}")
    if excluded_paths:
        print(f"  Excluded paths: {len(excluded_paths)}")

def find_overlap(s1, s2):
    """
    Finds the length of the overlapping suffix of s1 and prefix of s2.

    Args:
        s1 (str): First string.
        s2 (str): Second string.

    Returns:
        int: Length of the overlap.
    """
    for i in range(min(len(s1), len(s2)), 0, -1):
        if s1.endswith(s2[:i]):
            return i
    return 0

def slice_files(input_files, output_folder):
    """
    Slices a concatenated file back into individual files and folders.

    Args:
        input_files (list): List of input files to slice.
        output_folder (str): Path to the output folder.

    Returns:
        None
    """
    print(f"Slicing files: {', '.join(input_files)}")
    print(f"Output folder: {output_folder}")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output folder: {output_folder}")

    matches = []
    # Regular expression to match file sections in the concatenated file
    pattern = r'^\s*###\s*\*\*`([^`]+)`\*\*\s*$\n\n`(\w*)\n([\s\S]*?)(?:`|\Z)'

    for input_file in input_files:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        match_list = list(re.finditer(pattern, content, re.MULTILINE))
        matches.extend(match_list)

    # Group matches by base filename (handling numbered parts)
    file_groups = {}
    for match in matches:
        file_path = match.group(1).strip()
        parts = file_path.rsplit('.', 1)
        if len(parts) > 1 and parts[1].isdigit():
            base_path = parts[0]
            part_number = int(parts[1])
        else:
            base_path = file_path
            part_number = 0  # Use 0 for unnumbered files

        if base_path not in file_groups:
            file_groups[base_path] = []
        file_groups[base_path].append((part_number, match))

    # Process each group of files, combining numbered parts and handling overlaps
    processed_contents = {}
    for base_path, group in file_groups.items():
        sorted_group = sorted(group, key=lambda x: x[0])
        current_content = ""

        for i, (part_number, match) in enumerate(sorted_group):
            file_content = match.group(3)

            if i == 0:  # First part (base or .1)
                current_content = file_content
            else:
                overlap = find_overlap(current_content, file_content)
                if overlap > 0:
                    current_content += file_content[overlap:]
                else:
                    current_content += file_content

        # Store the final combined content
        processed_contents[base_path] = current_content

    # Write the processed contents to files, creating directories if needed
    for file_path, content in processed_contents.items():
        full_output_path = os.path.join(output_folder, file_path)
        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
        display_path = os.path.normpath(full_output_path)  # Normalize for better display
        print(f"  Creating file: {display_path}")
        with open(full_output_path, 'w', encoding='utf-8') as output_file:
            output_file.write(content)

    print("Slicing complete.")

def main():
    """
    Main function to handle command-line arguments and execute concatenation or slicing.

    This function parses command-line arguments, checks for duplicate names between files and folders,
    and executes either the concatenation or slicing operation based on the provided arguments.

    Args:
        None

    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        description="Concatenate or slice text files from files and folders into or from a single output with markdown code fences."
    )
    parser.add_argument("output", help="Name of the output file or output folder for slicing mode.")
    parser.add_argument(
        "paths", nargs="+", help="Files and/or folders to include (for concatenation) or files to slice apart."
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="Overwrite the output file if it exists."
    )
    parser.add_argument(
        "-s", "--slice", action="store_true", help="Slice the concatenated file back into individual files and folders."
    )
    parser.add_argument(
        "-x",
        "--exclude",
        action="append",
        default=[],
        help="Exclude files or folders matching the given pattern. Supports wildcards like '*' and '?'. Can be used multiple times.",
    )
    parser.add_argument(
        "-i",
        "--include",
        action="append",
        default=[],
        help="Include only files or folders matching the given pattern. Supports wildcards like '*' and '?'. Can be used multiple times.",
    )
    args = parser.parse_args()

    # Check for duplicate names between files and folders
    input_files = []
    input_folders = []
    for path in args.paths:
        if os.path.isfile(path):
            input_files.append(path)
        elif os.path.isdir(path):
            input_folders.append(path)
        else:
            print(f"Warning: '{path}' is neither a file nor a folder, skipping.")

    file_names = set(os.path.basename(f) for f in input_files)
    folder_names = set(os.path.basename(d) for d in input_folders)

    common_names = file_names & folder_names
    if common_names:
        handle_error(f"The following names are both files and folders: {', '.join(common_names)}")

    if args.slice:
        print("Running in slice mode...")
        slice_files(args.paths, args.output)
    else:
        print("Running in concatenate mode...")
        concatenate_files_and_folders(
            args.output, args.paths, force=args.force, exclusions=args.exclude, includes=args.include
        )

if __name__ == "__main__":
    main()
