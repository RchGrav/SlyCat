# SlyCat (Slice & Concatenate)

[![Slycat Logo](https://github.com/RchGrav/SlyCat/blob/main/assets/slycatlogo.png)](https://github.com/RchGrav/SlyCat)

Slycat is a powerful Python utility designed to simplify working with large language models (LLMs) on complex, multi-file projects. It seamlessly merges entire projects into a single Markdown-friendly document for easy submission to LLMs, and then intelligently slices LLM responses back into their original file structure.

## Key Features

* **Effortless Project Concatenation:** Combine multiple files and folders into a single Markdown file, maintaining the original file structure and applying relevant code fences based on file extensions.
* **Intelligent Response Slicing:**  Accurately parse LLM responses and restore the modified files back into their original directories, preserving the project's integrity.
* **Truncated Response Reassembly:** Handles LLM responses that are truncated or split into multiple parts, intelligently reassembling them into complete files.
* **Overlap Detection and Alignment:**  Detects and aligns overlapping sections in LLM responses, ensuring seamless integration of changes into your project.
* **Wide Range of File Support:** Handles various programming languages and file types, including Python, JavaScript, Bash, Markdown, and more, with appropriate code fences.
* **Flexible File Handling:**  Accommodates filenames with spaces and special characters, ensuring compatibility across diverse projects and platforms.
* **Streamlined LLM Workflow:** Facilitate the submission of large or complex codebases to LLMs for tasks like code generation, documentation, and review.
* **Efficient Project Reconstruction:**  Seamlessly rebuild your project with LLM-generated modifications, saving time and effort.
* **Selective File Exclusion:** Exclude specific files or folders from being included in the concatenation process, providing greater control over your LLM interactions.

## Installation

1. **Clone the Repository:**

   ```bash
   git clone [https://github.com/rchgrav/slycat.git](https://github.com/rchgrav/slycat.git)
   cd slycat
   ```

2. **Make the Script Executable:**

   ```bash
   chmod +x slycat.py
   ```

## Usage

### Concatenate Files and Folders

```bash
./slycat.py output_file.md [folder1] [script.py] [folder2] ... [-x excluded_file1 -x excluded_folder1]
```

* Replace `output_file.md` with the desired name for your concatenated Markdown file.
* List the files and folders you want to include.
* Use the `-x` or `--exclude` option to specify files or folders to exclude from the concatenation.

**Example:**

```bash
./slycat.py my_project.md my_code_folder utils.py -x my_code_folder/sensitive_data.txt
```

This example excludes the `sensitive_data.txt` file from being included in the concatenated output.

### Slice LLM Responses

1. **Include this prompt instruction when interacting with the LLM:**

   ```
   For each modified file, provide its full contents in a code fence.  Precede each fence with the relative filepath in the format: `### **`filepath`**`. If a file is truncated, append `.1`, `.2`, etc. to the filepath for each part, ensuring no content is omitted. Include all original code, even if unchanged. 
   ```

2. **Slice the Response:**

   ```bash
   ./slycat.py -s output_folder response_from_llm.md
   ```

   * Replace `output_folder` with the desired directory to store the restored files.
   * Replace `response_from_llm.md` with the Markdown file containing the LLM response.

**Example:**

```bash
./slycat.py -s updated_project llm_response.md
```

### Additional Options

* **Overwrite Existing Output:** Use the `-f` flag to force overwrite an existing output file.

## Supported File Types

Slycat applies appropriate code fences based on file extensions:

* Python (`.py`)
* JavaScript (`.js`)
* HTML (`.html`)
* CSS (`.css`)
* Bash (`.sh`)
* Java (`.java`)
* C++ (`.cpp`)
* C (`.c`)
* JSON (`.json`)
* YAML (`.yml`, `.yaml`)
* XML (`.xml`)
* Markdown (`.md`)

## Contributing

Contributions are welcome! Please fork the repository and submit pull requests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
