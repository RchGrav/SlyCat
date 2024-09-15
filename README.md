# Slycat

![Slycat Logo](https://github.com/RchGrav/SlyCat/blob/main/assets/slycat-logo.png)

Slycat is a super helpful tool designed to streamline interactions with large language models (LLMs) when working on multi-file projects. It enables you to easily merge entire projects into a single Markdown-friendly file for submission to LLMs, and then slice the LLM responses back into the original file structure.

## Features

- **Concatenate multiple files and directories** into a single Markdown file, preserving the original file structure and applying appropriate code fences based on file types.
- **Slice concatenated LLM responses** back into individual files and directories, reconstituting the project with its original file paths.
- **Supports various programming languages and file types**, ensuring proper Markdown formatting (including code fences) for Python, JavaScript, Bash scripts, Markdown, and more.
- **Handles filenames with spaces** and special characters, ensuring flexibility across different platforms and projects.
- **Efficient project submission** for LLMs: By merging all files into a single document, you can easily submit complex codebases or projects for LLM-based tasks like code generation, documentation, and reviews.
- **Rebuild projects effortlessly**: After receiving enhanced or generated code from an LLM, simply slice the response and restore your original folder and file structure.

## Installation

Clone this repository to your local machine:

```bash
git clone https://github.com/rchgrav/slycat.git
cd slycat
```

Make the script executable:

```bash
chmod +x slycat.py
```

Alternatively, run it with Python:

```bash
python slycat.py
```

## Usage

### Concatenate Files and Folders

To merge multiple files and folders into a single Markdown-friendly file, use the following command:

```bash
./slycat.py output_file.md folder1 script.py folder2
```

This will create a Markdown file (`output_file.md`) that includes all the text files from `folder1`, `script.py`, and `folder2`. The paths of each file will be preserved in the output, and code fences will be applied for non-Markdown files.

#### Example:

```bash
./slycat.py myproject_output.md ~/projects/mycode ~/scripts/utilities.py
```

This will generate a file called `myproject_output.md` that contains all the files from `mycode` and the `utilities.py` script in a single Markdown document, ready for submission to an LLM.

### Slice LLM Responses Back Into Files

Add the following line to your coding prompt...
```text
Provide the full contents of every modified file in a code fence, with the relative filepath in the format ### **`filepath`** above each fence, ensuring all original code (including unchanged sections) is included, and for long files, break them into logical sections with `.1`, `.2`, etc., without omitting any content.
```

After receiving the response from an LLM (such as code suggestions or documentation updates), you can slice the Markdown file back into individual files and directories:

```bash
./slycat.py -s output_folder concatenated_file.md
```

This command will create a directory (`output_folder`) where all the files will be restored based on their original paths.

#### Example:

```bash
./slycat.py -s restored_project myproject_output.md
```

This will restore the files from `myproject_output.md` into the `restored_project` directory.

### Overwrite an Existing Output File

If you need to overwrite an existing file during concatenation, use the `-f` (force) flag:

```bash
./slycat.py -f output_file.md folder1 script.py
```

## Example Workflow

1. **Concatenate your project** for submission to an LLM:

    ```bash
    ./slycat.py myproject_output.md ~/projects/mycode
    ```

2. **Submit the `myproject_output.md`** file to the LLM for review, code generation, or documentation completion.

3. **Receive the response** from the LLM and slice it back into files:

    ```bash
    ./slycat.py -s restored_project myproject_output.md
    ```

4. **The original folder structure and files** are restored in the `restored_project` folder, allowing you to continue working with the updated files.

## Supported File Types

Slycat supports the following file types and applies appropriate code fences based on their extensions:

- **Python (.py)**: `python`
- **JavaScript (.js)**: `javascript`
- **HTML (.html)**: `html`
- **CSS (.css)**: `css`
- **Bash (.sh)**: `bash`
- **Java (.java)**: `java`
- **C++ (.cpp)**: `cpp`
- **C (.c)**: `c`
- **JSON (.json)**: `json`
- **YAML (.yml/.yaml)**: `yaml`
- **XML (.xml)**: `xml`
- **Markdown (.md)**: `md`

Files without a supported extension will be added without code fences, preserving their plain text content.

## Contributing

We welcome contributions to Slycat! If you'd like to contribute, please follow these steps:

1. Fork the repository
2. Create a new branch (`git checkout -b feature-branch`)
3. Make your changes and commit them (`git commit -m 'Add some feature'`)
4. Push to the branch (`git push origin feature-branch`)
5. Open a pull request

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
