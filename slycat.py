#!/usr/bin/env python3

import os
import re
import chardet
import argparse

# Dictionary mapping file extensions to corresponding code fence languages
CODE_FENCE_LOOKUP = {
    ".py": "python",
    ".js": "javascript",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
    ".java": "java",
    ".cpp": "cpp",
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


def detect_encoding(file_path):
    """
    Detects the encoding of a file.

    Args:
        file_path (str): Path to the file.

    Returns:
        str: Detected encoding (e.g., 'utf-8', 'latin-1')
    """
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read(4096))
    return result['encoding']


def is_text_file(file_path):
    """
    Checks if a file is likely a text file based on its extension and content.

    Args:
        file_path (str): Path to the file.

    Returns:
        bool: True if it's likely a text file, False otherwise.
    """
    skip_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin'}
    _, ext = os.path.splitext(file_path)
    if ext.lower() in skip_extensions:
        return False
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
        result = chardet.detect(chunk)
        encoding = result['encoding']
        return (
            encoding is not None
            and result['confidence'] > 0.9
            and encoding.lower() != 'binary'
        )
    except Exception:
        return False


def write_file_to_output(file_path, base_folder, output_file):
    """
    Writes the content of a file to the output file with markdown code fences.

    Args:
        file_path (str): Path to the file.
        base_folder (str): Base folder for relative path calculation.
        output_file (file object): Output file object.
    """
    rel_path = os.path.relpath(file_path, base_folder)
    ext = os.path.splitext(file_path)[1]
    language = CODE_FENCE_LOOKUP.get(ext, "")
    detected_encoding = detect_encoding(file_path)
    encodings_to_try = [detected_encoding, 'utf-8', 'ascii', 'latin-1']
    content = None
    for encoding in encodings_to_try:
        if encoding is None:
            continue
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        print(
            f"Error: Unable to read {file_path} with any of the attempted encodings. Skipping this file."
        )
        return
    output_file.write(f"\n### **`{rel_path}`**\n\n`{language}\n{content}\n`\n")


def should_exclude(path, exclusions):
    """
    Checks if a path should be excluded based on the provided exclusions list.

    Args:
        path (str): Path to check.
        exclusions (list): List of exclusion patterns.

    Returns:
        bool: True if the path should be excluded, False otherwise
    """
    return any(
        os.path.abspath(path).startswith(os.path.abspath(excl)) for excl in exclusions
    )


def traverse_and_concatenate(base_folder, output_file, exclusions):
    """
    Traverses a directory recursively and concatenates text files to the output.

    Args:
        base_folder (str): Path to the base folder.
        output_file (file object): Output file object
        exclusions (list): List of exclusion patterns
    """
    for root, dirs, files in os.walk(base_folder):
        dirs[:] = [
            d
            for d in sorted(dirs)
            if not should_exclude(os.path.join(root, d), exclusions)
        ]
        files = [
            f for f in files if not should_exclude(os.path.join(root, f), exclusions)
        ]
        files.sort(
            key=lambda x: (
                x.lower() != "readme.md",
                not x.lower().endswith(".md"),
                x.lower(),
            )
        )
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path) and is_text_file(file_path):
                rel_path = os.path.relpath(file_path, base_folder)
                print(f"  Adding file: {rel_path}")
                write_file_to_output(file_path, base_folder, output_file)


def concatenate_files_and_folders(output_name, paths, force=False, exclusions=[]):
    """
    Concatenates text files and folders into a single output file with markdown code fences

    Args:
        output_name (str): Name of the output file
        paths (list): List of file and folder paths to concatenate
        force (bool): Overwrite the output file if it exists
        exclusions (list): List of exclusion patterns
    """
    if os.path.exists(output_name) and not force:
        print(
            f"Error: Output file '{output_name}' already exists. Use -f or --force to overwrite."
        )
        return
    print(f"Creating output file: {output_name}")
    with open(output_name, 'w', encoding='utf-8') as output_file:
        for path in paths:
            if should_exclude(path, exclusions):
                print(f"Excluding: {path}")
                continue
            if os.path.isfile(path):
                if is_text_file(path):
                    print(f"Processing file: {path}")
                    write_file_to_output(path, os.path.dirname(path), output_file)
                else:
                    print(f"Skipping non-text file: {path}")
            elif os.path.isdir(path):
                print(f"Processing directory: {path}")
                traverse_and_concatenate(path, output_file, exclusions)
            else:
                print(f"Warning: '{path}' is neither a file nor a folder, skipping.")
    print("Concatenation complete.")


def find_overlap(s1, s2):
    """
    Finds the length of the overlapping suffix of s1 and prefix of s2

    Args:
        s1 (str): First string
        s2 (str): Second string

    Returns
        int: Length of the overlap
    """
    for i in range(min(len(s1), len(s2)), 0, -1):
        if s1.endswith(s2[:i]):
            return i
    return 0


def slice_files(input_files, output_folder):
    """
    Slices a concatenated file back into individual files and folders

    Args:
        input_files (list): List of input files to slice
        output_folder (str): Path to the output folder
    """
    print(f"Slicing files: {', '.join(input_files)}")
    print(f"Output folder: {output_folder}")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output folder: {output_folder}")

    matches = []
    pattern = r'^\s*###\s*\*\*`([^`]+)`\*\*\s*$\n\n`(\w*)\n([\s\S]*?)(?:`|\Z)'

    for input_file in input_files:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        match_list = list(re.finditer(pattern, content, re.MULTILINE))
        matches.extend(match_list)

    # Group matches by base filename
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

    # Process each group of files
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

    # Write the processed contents to files
    for file_path, content in processed_contents.items():
        full_output_path = os.path.join(output_folder, file_path)
        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
        display_path = os.path.normpath(full_output_path)
        print(f"  Creating file: {display_path}")
        with open(full_output_path, 'w', encoding='utf-8') as output_file:
            output_file.write(content)

    print("Slicing complete.")


def main():
    """
    Main function to handle command-line arguments and execute concatenation or slicing.
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
        help="Exclude a file or folder from processing. Can be used multiple times.",
    )
    args = parser.parse_args()

    if args.slice:
        print("Running in slice mode...")
        slice_files(args.paths, args.output)
    else:
        print("Running in concatenate mode...")
        concatenate_files_and_folders(
            args.output, args.paths, force=args.force, exclusions=args.exclude
        )


if __name__ == "__main__":
    main()
