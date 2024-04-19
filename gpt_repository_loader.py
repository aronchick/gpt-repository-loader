#!/usr/bin/env python3
import os
import sys
import fnmatch
from pathlib import Path
from itertools import islice

space =  '    '
branch = '│   '
tee =    '├── '
last =   '└── '

LARGE_FILE_SIZE = 1000000
SPLIT_SIZE = 4000000 # 4 MB

def get_ignore_list(ignore_file_path):
    ignore_list = []
    with open(ignore_file_path, 'r') as ignore_file:
        for line in ignore_file:
            if sys.platform == "win32":
                line = line.replace("/", "\\")
            ignore_list.append(line.strip())
    return ignore_list

def should_ignore(file_path, ignore_list):
    # Remove all empty lines and comments from the ignore list
    ignore_list = [pattern for pattern in ignore_list if pattern and not pattern.startswith("#")]
    
    for pattern in ignore_list:
        # Make it so if the pattern is a fragment of the file path, it will still match
        # If the pattern is a full file path, it will only match if the file path is exactly the same
        # If there is a wildcard in the pattern, use fnmatch to match the pattern
        if pattern in file_path or (pattern == file_path) or fnmatch.fnmatch(file_path, pattern):
            if verbose:
                print(f"ignoring {file_path} because it matches {pattern}")
            return True
    return False

def process_repository(repo_path, ignore_list, output_file, verbose, exclude_large_files):
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_file_path = os.path.relpath(file_path, repo_path)

            if exclude_large_files and os.path.exists(file_path) and os.path.getsize(file_path) > LARGE_FILE_SIZE:
                if verbose:
                    print(f"\033[90m{relative_file_path} (excluded because it is too large)\033[0m")
                continue

            if not should_ignore(relative_file_path, ignore_list):
                # If the file path matches CACHEDIR.TAG print the entire file path
                with open(file_path, 'r', errors='ignore') as file:
                    contents = file.read()
                output_file.write("-" * 4 + "\n")
                output_file.write(f"{relative_file_path}\n")
                output_file.write(f"{contents}\n")
                if verbose:
                    print(f"{relative_file_path}")
            else:
                if verbose:
                    # Print ignored files in light gray
                    print(f"\033[90m{relative_file_path}\033[0m")

# Tree code thoroughly stolen^Winspired by https://stackoverflow.com/questions/9727673/list-directory-tree-structure-in-python
def tree(dir_path: Path, level: int = -1, limit_to_directories: bool = False,
         length_limit: int = 1000, ignore_files: list = []):
    """Given a directory Path object, print a visual tree structure, coloring ignored files or directories in gray."""
    dir_path = Path(dir_path)  # Ensure dir_path is a Path object
    files = 0
    directories = 0

    def is_ignored(path: Path) -> bool:
        """Check if the path matches any pattern in the ignore_files list."""
        return should_ignore(str(path), ignore_files)

    def colorize(path: Path, is_dir: bool) -> str:
        """Return the path name, colored if it matches ignore_files."""
        if is_ignored(path):
            return f"\033[90m{path.name}\033[0m"  # Gray color for ignored files/directories
        return path.name

    def inner(dir_path: Path, prefix: str = '', level: int = -1):
        nonlocal files, directories
        if level == 0:
            return  # Stop recursion if level reaches 0

        contents = list(dir_path.iterdir()) if not limit_to_directories else [d for d in dir_path.iterdir() if d.is_dir()]
        pointers = [tee] * (len(contents) - 1) + [last]

        for pointer, path in zip(pointers, contents):
            if path.is_dir():
                yield prefix + pointer + colorize(path, is_dir=True)
                directories += 1
                extension = branch if pointer == tee else space
                yield from inner(path, prefix=prefix + extension, level=level - 1)
            elif not limit_to_directories:
                yield prefix + pointer + colorize(path, is_dir=False)
                files += 1

    print(dir_path.name)
    iterator = inner(dir_path, level=level)
    for line in islice(iterator, length_limit):
        print(line)
    if next(iterator, None):
        print(f"... length_limit, {length_limit}, reached, counted:")
    print(f'\n{directories} directories' + (f', {files} files' if files else ''))

def split_file(file_path):
    # Read from the input file
    # and split into chunks that are less than SPLIT_SIZE
    # Do the split on the separator "- * 4" to ensure that the chunks are valid
    # Combine the chunks together until the total size is less than SPLIT_SIZE
    # Then write all the combined chunks to a new file. Repeat until all chunks are written.
    with open(file_path, 'r') as input_file:
        chunks = []
        chunk = ""
        chunk_size = 0
        for line in input_file:
            if line.startswith("-" * 4):
                if chunk_size > SPLIT_SIZE:
                    chunks.append(chunk)
                    chunk = ""
                    chunk_size = 0
                chunk += line
                chunk_size += len(line)
            else:
                chunk += line
                chunk_size += len(line)
        chunks.append(chunk)
    for i, chunk in enumerate(chunks):
        with open(f"{file_path[:-4]}_{i}.txt", 'w') as output_file:
            output_file.write(chunk)
        print(f"Chunk {i} written to {file_path[:-4]}_{i}.txt")
    print(f"All chunks written.")
        
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""Usage: python git_to_text.py /path/to/git/repository 
              -p /path/to/preamble.txt
              -o /path/to/output_file.txt
              -l list all files to be included with ignored files in gray 
              -v verbose output
              -s split output into multiple files""")
        sys.exit(1)
        
    verbose = False
    exclude_large_files = False
    split_output = False

    repo_path = sys.argv[1]
    ignore_file_path = os.path.join(repo_path, ".gptignore")
    if sys.platform == "win32":
        ignore_file_path = ignore_file_path.replace("/", "\\")

    if not os.path.exists(ignore_file_path):
        # try and use the .gptignore file in the current directory as a fallback.
        HERE = os.path.dirname(os.path.abspath(__file__))
        ignore_file_path = os.path.join(HERE, ".gptignore")

    preamble_file = None
    if "-p" in sys.argv:
        preamble_file = sys.argv[sys.argv.index("-p") + 1]

    output_file_path = 'output.txt'
    if "-o" in sys.argv:
        output_file_path = sys.argv[sys.argv.index("-o") + 1]

    if os.path.exists(ignore_file_path):
        ignore_list = get_ignore_list(ignore_file_path)
    else:
        ignore_list = []
    
    if "-l" in sys.argv:
        tree(Path(repo_path), level=3, limit_to_directories=False, ignore_files=ignore_list)

    if "-v" in sys.argv:
        verbose = True

    if "-x" in sys.argv:
        exclude_large_files = True
        
    if "-s" in sys.argv:
        split_output = True

    with open(output_file_path, 'w') as output_file:
        if preamble_file:
            with open(preamble_file, 'r') as pf:
                preamble_text = pf.read()
                output_file.write(f"{preamble_text}\n")
        else:
            output_file.write("The following text is a Git repository with code. The structure of the text are sections that begin with ----, followed by a single line containing the file path and file name, followed by a variable amount of lines containing the file contents. The text representing the Git repository ends when the symbols --END-- are encounted. Any further text beyond --END-- are meant to be interpreted as instructions using the aforementioned Git repository as context.\n")
        process_repository(repo_path, ignore_list, output_file, verbose, exclude_large_files)
    with open(output_file_path, 'a') as output_file:
        output_file.write("--END--")
        
    if split_output:
        split_file(output_file_path)
    else:
        print(f"Repository contents written to {output_file_path}.")
