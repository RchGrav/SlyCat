#!/usr/bin/env python3
"""
slycat.py

Concatenate (bundle) or slice (unbundle) project files into/from a single Markdown file
using ordered include/exclude rules (exact CLI order, last-match-wins), and safe output
handling to avoid overwriting source files.

Key fixes & features:
- **Never clobber source by accident**:
  - If OUTPUT looks like a directory (exists as dir, ends with /, or last component has no dot),
    we write to OUTPUT/bundle.md.
  - Refuses to write the bundle to the same path as any explicitly named input file.
  - Skips the bundle file itself if it happens to sit inside a walked tree.
  - Slice mode writes only inside the chosen OUTPUT_DIR and never escapes it.
- **Ordered rules**:
  - The order you pass `-i` / `-x` flags on the CLI is preserved. The last matching rule wins.
  - If at least one `-i` appears, default is EXCLUDE (only included stuff is in). Otherwise default is INCLUDE.
  - Directory-style matches work without globs: a rule like `src` applies to `.../src/...`.
- **Smarter filename detection for slicing**:
  - Checks the two lines above each code fence for common patterns:
      ### **`path/to/file.py`**
      ### `path/to/file.py`
      # `file.py` / # file.py
      File: "path/to/file.py" / Filename: 'file.py' / Path: `file.py`
      <!-- file: path/to/file.py -->   // file: path/to/file.js
      - `file.ext`
    and a general “quoted filename” heuristic.
  - If no name is found, files are named by language: file001.py, file002.js, file003.txt, ...

USAGE (concatenate, default):
  slycat.py OUTPUT [PATH ...] [-i PAT ...] [-x PAT ...] [-f] [--add-prompt]

  OUTPUT can be a file or a directory. If it's a directory (or looks like one),
  the bundle will be created as OUTPUT/bundle.md.

USAGE (slice):
  slycat.py -s OUTPUT_DIR BUNDLE.md [BUNDLE2.md ...] [-f]
"""

from __future__ import annotations
import argparse
import fnmatch
import os
import re
import sys
import itertools
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Dict

# ---------- language ↔ extension helpers ----------

LANG_TO_EXT = {
    "python": ".py", "py": ".py", "ipython": ".py",
    "bash": ".sh", "sh": ".sh", "zsh": ".sh",
    "powershell": ".ps1", "ps1": ".ps1",
    "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts", "tsx": ".tsx", "jsx": ".jsx",
    "json": ".json",
    "yaml": ".yml", "yml": ".yml",
    "toml": ".toml",
    "ini": ".ini",
    "xml": ".xml",
    "html": ".html",
    "css": ".css", "scss": ".scss", "less": ".less",
    "go": ".go",
    "rust": ".rs", "rs": ".rs",
    "java": ".java",
    "kotlin": ".kt", "kt": ".kt",
    "c": ".c", "cpp": ".cpp", "c++": ".cpp", "hpp": ".hpp", "h": ".h",
    "swift": ".swift",
    "ruby": ".rb", "rb": ".rb",
    "php": ".php",
    "scala": ".scala",
    "r": ".R",
    "matlab": ".m", "m": ".m",
    "dockerfile": "",           # special
    "makefile": "",             # special
    "cmake": "CMakeLists.txt",  # special-ish
    "text": ".txt", "txt": ".txt",
    "markdown": ".md", "md": ".md",
    "graphql": ".graphql",
    "proto": ".proto",
    "sql": ".sql",
    "nginx": ".conf", "conf": ".conf",
}

EXT_TO_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "tsx", ".jsx": "jsx",
    ".json": "json", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml", ".ini": "ini",
    ".xml": "xml", ".html": "html", ".css": "css", ".scss": "scss", ".less": "less",
    ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin", ".c": "c", ".cpp": "cpp",
    ".hpp": "cpp", ".h": "c", ".swift": "swift", ".rb": "ruby", ".php": "php", ".scala": "scala",
    ".R": "r", ".m": "matlab", ".Dockerfile": "dockerfile", "Dockerfile": "dockerfile",
    ".Makefile": "makefile", "Makefile": "makefile", ".md": "markdown", ".txt": "text",
    ".graphql": "graphql", ".proto": "proto", ".sql": "sql", ".conf": "conf",
}

BINARY_EXTS = {
    '.jpg','.jpeg','.png','.gif','.bmp','.tiff','.ico',
    '.zip','.rar','.7z','.tar','.gz','.bz2','.xz',
    '.pdf','.exe','.dll','.so','.dylib','.class','.o','.a',
    '.pyc','.pyo','.pdb','.db','.sqlite','.woff','.woff2','.ttf','.eot',
}

# ---------- utility ----------

def is_probably_text_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    if ext in BINARY_EXTS:
        return False
    try:
        with open(path, 'rb') as f:
            chunk = f.read(4096)
        if not chunk:
            return True
        if b'\x00' in chunk:
            return False
        ctrl = sum(1 for b in chunk if b < 9 or (13 < b < 32))
        return (ctrl / max(1, len(chunk))) < 0.08
    except Exception:
        return False

def read_text_best_effort(path: str) -> Optional[str]:
    for enc in ('utf-8-sig','utf-8','cp1252','latin-1','ascii'):
        try:
            with open(path, 'r', encoding=enc, errors='strict') as f:
                return f.read()
        except Exception:
            continue
    return None

def write_text(path: str, text: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

def norm_posix(path: str) -> str:
    return os.path.normpath(path).replace(os.sep, '/')

def looks_like_directory_string(s: str) -> bool:
    if os.path.isdir(s):
        return True
    if s.endswith(('/', '\\')):
        return True
    last = os.path.basename(s.rstrip('/\\'))
    return '.' not in last  # dotless → treat as dir-like

# ---------- rules ----------

@dataclass
class Rule:
    action: str     # 'include' or 'exclude'
    pattern: str

def _pattern_matches_path(pattern: str, path: str) -> bool:
    """
    Match against:
      - full path and basename via fnmatch,
      - any path-segment equality (so 'src' matches 'a/b/src/c/d.py'),
      - directory prefix (so 'src/utils' matches 'src/utils/..').
    Paths are normalized to forward slashes.
    """
    p = pattern.strip().strip('/').replace('\\','/')
    s = path.strip('/').replace('\\','/')

    # glob on full path and basename
    if fnmatch.fnmatch(s, p) or fnmatch.fnmatch(os.path.basename(s), p):
        return True

    # path-segment equality
    if p in s.split('/'):
        return True

    # directory/prefix match
    if s == p or s.startswith(p + '/'):
        return True

    # if pattern endswith '/', treat like dir
    if pattern.endswith('/') and (s == p or s.startswith(p + '/')):
        return True

    return False

def last_match_wins(path: str, is_dir: bool, ordered_rules: List[Rule]) -> Optional[bool]:
    """
    Return True/False for include/exclude if any rule matched; otherwise None.
    Rules are evaluated in the exact CLI order; the LAST matching rule wins.
    """
    decision: Optional[bool] = None
    for rule in ordered_rules:
        if _pattern_matches_path(rule.pattern, path):
            decision = (rule.action == 'include')
    return decision

def effective_include(path: str, is_dir: bool, ordered_rules: List[Rule]) -> bool:
    decision = last_match_wins(path, is_dir, ordered_rules)
    if decision is not None:
        return decision
    # default if no rule matched
    default_is_include = not any(r.action == 'include' for r in ordered_rules)
    return default_is_include

# ---------- concatenate ----------

def language_for_extension(ext: str) -> str:
    return EXT_TO_LANG.get(ext, 'text')

def fence_for_content(content: str) -> str:
    return '````' if '```' in content else '```'

def write_file_section(bundle, relpath: str, language: str, content: str) -> None:
    fence = fence_for_content(content)
    lang = language if language else ''
    bundle.write(f"### **`{relpath}`**\n\n{fence}{lang}\n{content}\n{fence}\n\n")

def traverse_and_collect(root: str,
                         base_for_rel: str,
                         bundle_path: str,
                         ordered_rules: List[Rule]) -> Iterable[Tuple[str,str,str]]:
    junk = {'.git', '.svn', '.hg', '.DS_Store', '__pycache__', 'node_modules', '.idea', '.vscode'}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # prune obvious junk unless user explicitly matched it later (they still can via direct -i)
        dirnames[:] = [d for d in dirnames if d not in junk]

        for name in filenames:
            full = os.path.join(dirpath, name)
            if os.path.normpath(full) == os.path.normpath(bundle_path):
                continue  # don't include the output file inside itself
            if not is_probably_text_file(full):
                continue

            # rel path from base
            rel_from_base = os.path.relpath(full, base_for_rel)
            base_name = os.path.basename(os.path.normpath(base_for_rel))
            relpath = os.path.join(base_name, rel_from_base) if base_name and base_name != '.' else rel_from_base
            relpath = norm_posix(relpath)

            if not effective_include(relpath, False, ordered_rules):
                continue

            content = read_text_best_effort(full)
            if content is None:
                continue
            language = language_for_extension(os.path.splitext(full)[1])
            yield relpath, language, content

# ---------- slice (unbundle) ----------

FENCE_OPEN_RE = re.compile(r'^[ \t]*```+([A-Za-z0-9_-]+)?[ \t]*$', re.MULTILINE)
FENCE_CLOSE_RE = re.compile(r'^[ \t]*```+[ \t]*$', re.MULTILINE)

HEADER_PATTERNS = [
    re.compile(r'^\s*###\s*\*\*`(?P<name>[^`]+)`\*\*\s*$', re.MULTILINE),
    re.compile(r'^\s*###\s*`(?P<name>[^`]+)`\s*$', re.MULTILINE),
    re.compile(r'^\s*#\s*`(?P<name>[^`]+)`\s*$', re.MULTILINE),
    re.compile(r'^\s*#\s*(?P<name>[^`"\'#]+?\.[A-Za-z0-9]{1,8})\s*$', re.MULTILINE),
    re.compile(r'^\s*(?:File|Filename|Path)\s*:\s*[`"\']?(?P<name>[^`"\']+?\.[A-Za-z0-9]{1,8})[`"\']?\s*$', re.MULTILINE),
    re.compile(r'^\s*<!--\s*file\s*:\s*(?P<name>[^>]+?\.[A-Za-z0-9]{1,8})\s*-->\s*$', re.MULTILINE),
    re.compile(r'^\s*//\s*file\s*:\s*(?P<name>[^ \t]+?\.[A-Za-z0-9]{1,8})\s*$', re.MULTILINE),
    re.compile(r'^\s*\[(?P<name>[^\]]+?\.[A-Za-z0-9]{1,8})\]\s*$', re.MULTILINE),
    re.compile(r'^\s*-\s*`(?P<name>[^`]+?\.[A-Za-z0-9]{1,8})`.*$', re.MULTILINE),
]

# Heuristic: in the two lines above the fence, find anything in quotes/backticks that looks like a filename
QUOTED_FILENAME_NEARBY = re.compile(
    r'[`"\']\s*([A-Za-z0-9_.\- /\\]+?\.[A-Za-z0-9]{1,8})\s*[`"\']'
)

def sanitize_relpath(name: str, language_hint: str, per_ext_counters: Dict[str,int]) -> str:
    name = (name or '').strip().strip('`"\'')
    name = name.replace('\\', '/')
    name = re.sub(r'\s+', ' ', name)
    name = name.lstrip('/')
    # drop any .. segments
    parts = []
    for p in name.split('/'):
        if p in ('', '.'):
            continue
        if p == '..':
            continue
        parts.append(p)
    name = '/'.join(parts)

    # if name looks like a directory, add extension from hint
    base = os.path.basename(name)
    if '.' not in base:
        ext = LANG_TO_EXT.get((language_hint or '').lower(), '.txt')
        if ext and not base.lower().endswith((ext or '').lower()):
            if ext in ('Dockerfile','Makefile','CMakeLists.txt',''):
                pass
            else:
                name = f"{name}{ext}"
    return name or default_name(language_hint, per_ext_counters)

def default_name(language_hint: str, per_ext_counters: Dict[str,int]) -> str:
    ext = LANG_TO_EXT.get((language_hint or '').lower(), '.txt')
    if ext in ('Dockerfile', 'Makefile', 'CMakeLists.txt'):
        base = ext
        ext_part = ''
        key = ext
    else:
        base = 'file'
        ext_part = ext or ''
        key = ext or '.txt'
    n = per_ext_counters.get(key, 0) + 1
    per_ext_counters[key] = n
    return f"{base}{n:03d}{ext_part}" if base == 'file' else base

def detect_name_from_context(text: str, fence_start_idx: int) -> Optional[str]:
    """
    Look back up to two lines above fence_start_idx for headers or quoted filenames.
    """
    start = text.rfind('\n', 0, fence_start_idx)
    if start == -1: start = 0
    prev1_end = start
    prev1_start = text.rfind('\n', 0, prev1_end) + 1 if prev1_end > 0 else 0
    prev2_start = text.rfind('\n', 0, prev1_start-1) + 1 if prev1_start > 0 else 0

    context = text[prev2_start:prev1_end]
    for pat in HEADER_PATTERNS:
        m_iter = list(pat.finditer(context))
        if m_iter:
            return m_iter[-1].group('name').strip()  # nearest match

    q = QUOTED_FILENAME_NEARBY.search(context)
    if q:
        return q.group(1).strip()

    return None

def slice_bundle_to_dir(bundle_path: str, out_dir: str, force: bool=False) -> Tuple[int,int]:
    text = read_text_best_effort(bundle_path)
    if text is None:
        raise RuntimeError(f"Cannot read {bundle_path} as text.")

    # Optionally skip an initial AI instruction blockquote (until blank line)
    if text.lstrip().startswith('>'):
        lines = text.splitlines(keepends=True)
        idx = 0
        while idx < len(lines) and lines[idx].lstrip().startswith('>'):
            idx += 1
        while idx < len(lines) and lines[idx].strip() == '':
            idx += 1
        text = ''.join(lines[idx:])

    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    per_ext_counters: Dict[str,int] = {}
    files_created = 0
    files_skipped = 0

    pos = 0
    while True:
        m_open = FENCE_OPEN_RE.search(text, pos)
        if not m_open:
            break
        lang = (m_open.group(1) or 'text').lower()
        m_close = FENCE_CLOSE_RE.search(text, m_open.end())
        if not m_close:
            break

        content = text[m_open.end():m_close.start()]
        if content.startswith('\n'):
            content = content[1:]

        raw_name = detect_name_from_context(text, m_open.start())
        rel_name = sanitize_relpath(raw_name, lang, per_ext_counters) if raw_name else default_name(lang, per_ext_counters)

        # never allow path to escape out_dir
        safe_rel = '/'.join(part for part in rel_name.split('/') if part not in ('', '.', '..'))
        dest = os.path.join(out_dir, safe_rel)

        final_dest = dest
        if not force and os.path.exists(final_dest):
            base, ext = os.path.splitext(final_dest)
            k = 1
            while os.path.exists(f"{base}-{k}{ext}"):
                k += 1
            final_dest = f"{base}-{k}{ext}"

        write_text(final_dest, content)
        files_created += 1
        pos = m_close.end()

    return files_created, files_skipped

# ---------- CLI ----------

def resolve_output_for_concat(output_arg: str) -> str:
    # If path is a directory or looks like one, use bundle.md inside it
    if looks_like_directory_string(output_arg):
        out_dir = output_arg
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, 'bundle.md')
        return os.path.abspath(out_file)
    parent = os.path.dirname(output_arg) or '.'
    os.makedirs(parent, exist_ok=True)
    return os.path.abspath(output_arg)

def _ordered_rules_from_argv(argv: List[str]) -> List[Rule]:
    rules: List[Rule] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ('-i', '--include') and i + 1 < len(argv):
            rules.append(Rule('include', argv[i+1]))
            i += 2
            continue
        if tok in ('-x', '--exclude') and i + 1 < len(argv):
            rules.append(Rule('exclude', argv[i+1]))
            i += 2
            continue
        i += 1
    return rules

def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser(
        description="Concatenate or slice project files into/from a Markdown bundle safely.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    p.add_argument("output",
                   help="Concatenate: output file OR directory for the bundle. "
                        "Slice: output directory for extracted files.")
    p.add_argument("paths", nargs="+",
                   help="Concat: roots (files/dirs) to include. Slice: one or more bundle files to slice.")
    p.add_argument("-i","--include", action="append", default=[], dest="includes",
                   help="Include pattern (glob or path-segment). Repeatable. Last match wins.")
    p.add_argument("-x","--exclude", action="append", default=[], dest="excludes",
                   help="Exclude pattern (glob or path-segment). Repeatable. Last match wins.")
    p.add_argument("-f","--force", action="store_true",
                   help="Overwrite existing output file (concat) or extracted files (slice).")
    p.add_argument("-s","--slice", action="store_true",
                   help="Slice mode (extract files from bundle into OUTPUT directory).")
    p.add_argument("--add-prompt", action="store_true",
                   help="Prepend a short instruction block to the bundle (concat mode).")

    args = p.parse_args(argv)
    ordered_rules = _ordered_rules_from_argv(argv)

    if args.slice:
        out_dir = os.path.abspath(args.output)
        if os.path.isfile(out_dir):
            p.error("In slice mode, OUTPUT must be a directory.")
        os.makedirs(out_dir, exist_ok=True)
        total = 0
        for bundle in args.paths:
            created, _ = slice_bundle_to_dir(bundle, out_dir, force=args.force)
            print(f"Sliced {bundle}: {created} files")
            total += created
        print(f"Done. Total files created: {total}")
        return 0

    # Concatenate mode
    out_file = resolve_output_for_concat(args.output)

    # Collect explicit input files and directory roots
    input_files: List[str] = []
    input_roots: List[str] = []
    for pth in args.paths:
        if not os.path.exists(pth):
            print(f"Warning: input path does not exist: {pth}")
            continue
        if os.path.isfile(pth):
            input_files.append(os.path.abspath(pth))
        else:
            input_roots.append(os.path.abspath(pth))

    # Hard safety: do not overwrite an explicitly listed input file
    if os.path.abspath(out_file) in set(input_files):
        raise SystemExit(f"Refusing to overwrite input file with bundle: {out_file}")

    if os.path.exists(out_file) and not args.force:
        raise SystemExit(f"Output bundle exists (use -f to overwrite): {out_file}")

    with open(out_file, 'w', encoding='utf-8') as bundle:
        if args.add_prompt:
            bundle.write(
                (
                    "> **AI Instruction:**\n"
                    "> The following bundle lists files with headers of the form:\n"
                    "> `### **`path/to/file.ext`**` followed by a fenced code block.\n"
                    ">\n"
                    "> Keep the format intact when editing.\n\n"
                )
            )

        for root in args.paths:
            if not os.path.exists(root):
                print(f"Skipping missing: {root}")
                continue
            if os.path.isfile(root):
                base_for_rel = os.path.dirname(root) or '.'
                rel_from_base = os.path.relpath(root, base_for_rel)
                base_name = os.path.basename(os.path.normpath(base_for_rel))
                relpath = os.path.join(base_name, rel_from_base) if base_name and base_name != '.' else rel_from_base
                relpath = norm_posix(relpath)
                if effective_include(relpath, False, ordered_rules):
                    content = read_text_best_effort(root)
                    if content is not None:
                        write_file_section(bundle, relpath, language_for_extension(os.path.splitext(root)[1]), content)
                        print(f"Added file: {relpath}")
                else:
                    print(f"Excluded file by rules: {relpath}")
            else:
                base_for_rel = os.path.abspath(root)
                for relpath, lang, content in traverse_and_collect(root, base_for_rel, out_file, ordered_rules):
                    write_file_section(bundle, relpath, lang, content)
                    print(f"Added: {relpath}")

    print(f"Bundle written: {out_file}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
