#!/usr/bin/env python3
import os
import re
import chardet
import argparse

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
    """Detect the encoding of a file."""
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read(4096))
    return result['encoding']

def is_text_file(file_path):
    """Check if the file is a text file by its extension and content."""

    skip_extensions = {'.pyc', '.pyo', '.so', '.dll', '.exe', '.bin'}

    _, ext = os.path.splitext(file_path)
    if ext.lower() in skip_extensions:
        return False

    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
        result = chardet.detect(chunk)
        encoding = result['encoding']

        return encoding is not None and result['confidence'] > 0.9 and encoding.lower() != 'binary'
    except Exception:

        return False

def write_file_to_output(file_path, base_folder, output_file):
    """Write the contents of a file to the output file with proper code fences."""
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
        print(f"Error: Unable to read {file_path} with any of the attempted encodings. Skipping this file.")
        return

    output_file.write(f"\n### **`{rel_path}`**\n\n")
    if language == "md":
        output_file.write(f"{content}\n\n")
    else:
        output_file.write(f"```{language}\n{content}\n```\n")

def traverse_and_concatenate(base_folder, output_file):
    """Recursively traverse folders and concatenate text files."""
    for root, dirs, files in os.walk(base_folder):
        dirs.sort()
        files.sort(key=lambda x: (x != "README.md", not x.endswith(".md"), x.lower()))
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path) and is_text_file(file_path):
                print(f"  Adding file: {file_path}")
                write_file_to_output(file_path, base_folder, output_file)

def concatenate_files_and_folders(output_name, paths, force=False):
    """Main function to process the given paths."""
    if os.path.exists(output_name) and not force:
        print(f"Error: Output file '{output_name}' already exists. Use -f or --force to overwrite.")
        return

    print(f"Creating output file: {output_name}")
    with open(output_name, 'w', encoding='utf-8') as output_file:
        for path in paths:
            if os.path.isfile(path):
                if is_text_file(path):
                    print(f"Processing file: {path}")
                    write_file_to_output(path, os.path.dirname(path), output_file)
                else:
                    print(f"Skipping non-text file: {path}")
            elif os.path.isdir(path):
                print(f"Processing directory: {path}")
                traverse_and_concatenate(path, output_file)
            else:
                print(f"Warning: '{path}' is neither a file nor a folder, skipping.")
    print("Concatenation complete.")

def slice_file(input_file, output_folder):
    """Parse the concatenated file and reconstruct individual files with folder structure."""
    print(f"Slicing file: {input_file}")
    print(f"Output folder: {output_folder}")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output folder: {output_folder}")

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'^\s*###\s*\*\*`([^`]+)`\*\*\s*$\n\n(?:```(\w*)\n([\s\S]*?)```|([\s\S]*?)(?=\n###\s|\Z))'
    matches = re.finditer(pattern, content, re.MULTILINE)

    for match in matches:
        file_path = match.group(1).strip()
        code_fence_language = match.group(2)
        fenced_content = match.group(3)
        plain_content = match.group(4)

        full_output_path = os.path.join(output_folder, file_path)
        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)

        display_path = os.path.normpath(full_output_path)
        print(f"  Creating file: {display_path}")


        with open(full_output_path, 'w', encoding='utf-8') as output_file:
            if fenced_content:
                output_file.write(fenced_content.strip())
            elif plain_content:
                output_file.write(plain_content.strip())

    print("Slicing complete.")

def main():
    parser = argparse.ArgumentParser(description="Concatenate or slice text files from files and folders into or from a single output with markdown code fences.")

    parser.add_argument("output", help="Name of the output file or output folder for slicing mode.")
    parser.add_argument("paths", nargs="+", help="Files and/or folders to include (for concatenation) or files to slice apart.")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite the output file if it exists.")
    parser.add_argument("-s", "--slice", action="store_true", help="Slice the concatenated file back into individual files and folders.")

    args = parser.parse_args()

    if args.slice:
        print("Running in slice mode...")
        for path in args.paths:
            slice_file(path, args.output)
    else:
        print("Running in concatenate mode...")
        concatenate_files_and_folders(args.output, args.paths, force=args.force)

if __name__ == "__main__":
    main()
