#!/usr/bin/env python3
import os
import re
import chardet
import argparse

# Define common file extensions and their corresponding code fence labels
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
    ".md": "md",  # Special case: Markdown files are not enclosed in code fences
}

def detect_encoding(file_path):
    """Detect the encoding of a file."""
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read(4096))  # Read the first 4KB to detect encoding
    return result['encoding']

def is_text_file(file_path):
    """Check if the file is a text file by its encoding."""
    encoding = detect_encoding(file_path)
    return encoding is not None and encoding.lower() not in ['binary', None]

def write_file_to_output(file_path, base_folder, output_file):
    """Write the contents of a file to the output file with proper code fences."""
    rel_path = os.path.relpath(file_path, base_folder)
    ext = os.path.splitext(file_path)[1]
    language = CODE_FENCE_LOOKUP.get(ext, "")

    with open(file_path, 'r', encoding=detect_encoding(file_path)) as f:
        content = f.read()

    # Add the path tag with triple ### and proper fencing
    output_file.write(f"\n### **`{rel_path}`**\n\n")
    if language == "md":
        output_file.write(f"{content}\n\n")
    else:
        output_file.write(f"```{language}\n{content}\n```\n")

def traverse_and_concatenate(base_folder, output_file):
    """Recursively traverse folders and concatenate text files."""
    for root, _, files in os.walk(base_folder):
        # Sort files: README.md first, then other .md files, then the rest alphabetically
        files.sort(key=lambda x: (x != "README.md", not x.endswith(".md"), x.lower()))
        
        for file in files:
            file_path = os.path.join(root, file)

            if os.path.isfile(file_path) and is_text_file(file_path):
                write_file_to_output(file_path, base_folder, output_file)

def concatenate_files_and_folders(output_name, paths, force=False):
    """Main function to process the given paths."""
    if os.path.exists(output_name) and not force:
        print(f"Error: Output file '{output_name}' already exists. Use -f or --force to overwrite.")
        return

    with open(output_name, 'w', encoding='utf-8') as output_file:
        for path in paths:
            if os.path.isfile(path):
                if is_text_file(path):
                    write_file_to_output(path, os.path.dirname(path), output_file)
            elif os.path.isdir(path):
                traverse_and_concatenate(path, output_file)
            else:
                print(f"Warning: '{path}' is neither a file nor a folder, skipping.")

def slice_file(input_file, output_folder):
    """Parse the concatenated file and reconstruct individual files."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Updated regex to allow spaces in filenames and to be more forgiving with formatting
    pattern = r'^\s*###\s*[`\'"*]*([^\n`\'"*]+)[`\'"*]*\s*$(?:\n|\r\n)*\n(?:```(\w*)\n([\s\S]*?)```|([\s\S]*?)(?=\n###\s|$))'
    
    matches = re.finditer(pattern, content, re.MULTILINE)
    
    for match in matches:
        file_path = match.group(1).strip()  # Extracted file path
        code_fence_language = match.group(2)  # Language detected in code fence (if any)
        fenced_content = match.group(3)  # Content inside code fences (if any)
        plain_content = match.group(4)  # Plain content (if not inside code fence)

        # Create the directory structure in the output folder
        full_output_path = os.path.join(output_folder, file_path)
        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)

        if fenced_content:
            # If there is fenced content (inside ```language```), write the file with correct extension
            extension = {v: k for k, v in CODE_FENCE_LOOKUP.items()}.get(code_fence_language, ".txt")
            with open(full_output_path + extension, 'w', encoding='utf-8') as output_file:
                output_file.write(fenced_content.strip())
        elif plain_content:
            # If it is plain markdown content, just write it as is
            with open(full_output_path, 'w', encoding='utf-8') as output_file:
                output_file.write(plain_content.strip())

def main():
    parser = argparse.ArgumentParser(description="Concatenate or slice text files from files and folders into or from a single output with markdown code fences.")
    
    parser.add_argument("output", help="Name of the output file or output folder for slicing mode.")
    parser.add_argument("paths", nargs="+", help="Files and/or folders to include (for concatenation) or files to slice apart.")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite the output file if it exists.")
    parser.add_argument("-s", "--slice", action="store_true", help="Slice the concatenated file back into individual files and folders.")
    
    args = parser.parse_args()

    if args.slice:
        # Slicing mode: Split a concatenated file into individual files
        for path in args.paths:
            slice_file(path, args.output)
    else:
        # Concatenation mode: Concatenate files and folders into a single output
        concatenate_files_and_folders(args.output, args.paths, force=args.force)

if __name__ == "__main__":
    main()
