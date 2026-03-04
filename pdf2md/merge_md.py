
from pathlib import Path
import sys


def merge_markdown_files(paths, output_file_path, separator="\n\n"):
    """
    合并多个Markdown文件为一个文件
    
    Args:
        paths (list): 要合并的Markdown文件路径列表
        output_path (str): 输出文件的路径
        separator (str): 用于分隔各Markdown内容的分隔符
    
    Raises:
        SystemExit: 当没有可合并的内容时
    """
    parts = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            print(f"warning: {p} not found, skipping", file=sys.stderr)
            continue
        text = p.read_text(encoding="utf-8")
        parts.append(text.rstrip())
    if not parts:
        raise SystemExit("No markdown content to write.")
    out = Path(output_file_path)
    out.write_text((separator.join(parts)).rstrip() + "\n", encoding="utf-8")
    return out


def gather_paths_from_dir(directory, sort_key='name'):
    """
    从指定目录中收集Markdown文件并按指定方式排序
    
    Args:
        directory (str): 要搜索的目录路径
        sort_key (str): 排序方式，"name"按文件名排序，"mtime"按修改时间排序
    
    Returns:
        list: 排序后的Markdown文件路径列表
    """
    p = Path(directory)
    md_files = list(p.glob("*.md"))
    if sort_key == "name":
        md_files.sort(key=lambda x: x.name)
    elif sort_key == "mtime":
        md_files.sort(key=lambda x: x.stat().st_mtime)
    return md_files



