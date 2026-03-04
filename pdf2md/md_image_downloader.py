import re
import os
import requests
import base64
from pathlib import Path
from urllib.parse import urlsplit, unquote

IMG_MD_RE = re.compile(r'!\[([^\]]*)\]\(\s*(<)?(?P<url>[^>\s)]+)(?(2)>)(?:\s+"[^"]*")?\s*\)')
IMG_HTML_RE = re.compile(r'<img[^>]+src=["\'](?P<url>[^"\']+)["\'][^>]*>')


def sanitize_filename(name: str) -> str:
    """
    清理文件名，移除或替换不合法的字符
    
    Args:
        name (str): 原始文件名
    
    Returns:
        str: 清理后的安全文件名
    """
    name = unquote(name)
    name = name.replace('\\', '_').replace('/', '_')
    name = re.sub(r'[^0-9A-Za-z._-]', '_', name)
    return name


def ext_from_content_type(content_type: str) -> str:
    """
    根据内容类型(Content-Type)返回对应的文件扩展名
    
    Args:
        content_type (str): 内容类型字符串，如 "image/jpeg"
    
    Returns:
        str: 对应的文件扩展名，如 ".jpg"。如果内容类型不在映射表中，返回空字符串
    """
    if not content_type:
        return ''
    content_type = content_type.split(';')[0].strip().lower()
    mapping = {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/svg+xml': '.svg',
        'image/bmp': '.bmp',
    }
    return mapping.get(content_type, '')


def save_data_uri(data_uri: str, dest: Path) -> Path:
    """
    将data URI格式的图片数据保存到文件
    
    Args:
        data_uri (str): data URI格式的图片数据，格式为 "data:[<mediatype>][;base64],<data>"
        dest (Path): 目标文件路径
    
    Returns:
        Path: 保存后的文件路径
    """
    # data:[<mediatype>][;base64],<data>
    header, b64data = data_uri.split(',', 1)
    if ';base64' in header:
        raw = base64.b64decode(b64data)
    else:
        raw = unquote(b64data).encode('utf-8')
    # try to get extension from mediatype
    m = re.match(r'data:(?P<type>[^;]+)', header)
    ext = ''
    if m:
        ext = ext_from_content_type(m.group('type'))
    if not dest.suffix and ext:
        dest = dest.with_suffix(ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'wb') as f:
        f.write(raw)
    return dest


def download_url(url: str, dest: Path, session: requests.Session = None) -> Path:
    """
    从URL下载图片并保存到指定位置
    
    Args:
        url (str): 图片URL或data URI
        dest (Path): 目标文件路径
        session (requests.Session, optional): 可选的requests会话对象，用于复用连接
    
    Returns:
        Path: 保存后的文件路径
    
    Raises:
        requests.HTTPError: 当HTTP请求返回错误状态码时
    """
    if url.startswith('data:'):
        return save_data_uri(url, dest)

    s = session or requests
    r = s.get(url, stream=True, timeout=30)
    r.raise_for_status()
    # try to determine extension
    ext = Path(urlsplit(url).path).suffix
    if not ext:
        ext = ext_from_content_type(r.headers.get('Content-Type', ''))
    if not dest.suffix and ext:
        dest = dest.with_suffix(ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
    return dest


def convert_image_local(md_path: str,backup=False):
    """
    处理Markdown文件，下载其中的图片并替换为本地路径
    
    Args:
        md_path (str): Markdown文件路径
        backup (bool, optional): 是否创建原始文件的备份。默认为False
    
    Returns:
        dict: 原始URL到本地路径的映射字典
    
    Note:
        - 支持Markdown格式(![]())和HTML格式(<img src="">)的图片引用
        - 会创建一个与Markdown文件同名加"_images"的文件夹存放下载的图片
        - 处理过的文件会更新图片链接为相对本地路径
    """
    file_dir, file_name = os.path.split(md_path)
    file_base, file_ext = os.path.splitext(file_name)
    new_folder_path = os.path.join(file_dir, file_base+'_images')
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)
    images_root = Path(new_folder_path)
    text=Path(md_path).read_text(encoding='utf-8')
    session = requests.Session()
    seen = {}
    counter = 1
    md_path = Path(md_path)
    def replace_url(match):
        nonlocal counter
        url = match.group('url')
        if url.startswith('file:'):
            return match.group(0)
        if url in seen:
            new = seen[url]
            return match.group(0).replace(url, new)

        # build filename
        parsed = urlsplit(url)
        name = Path(unquote(parsed.path)).name or f'image_{counter}'
        name = sanitize_filename(name)
        dest = images_root / name
        # ensure unique
        if dest.exists():
            stem = dest.stem
            suff = dest.suffix
            dest = images_root / f"{stem}_{counter}{suff}"

        try:
            saved = download_url(url, dest, session=session)
        except Exception:
            return match.group(0)

        rel = os.path.relpath(saved, md_path.parent).replace('\\', '/')
        seen[url] = rel
        counter += 1
        return match.group(0).replace(url, rel)

    # first replace markdown-style images
    text2 = IMG_MD_RE.sub(replace_url, text)
    # then html <img> tags
    def replace_html(m):
        nonlocal counter
        url = m.group('url')
        if url in seen:
            new = seen[url]
            return m.group(0).replace(url, new)
        parsed = urlsplit(url)
        name = Path(unquote(parsed.path)).name or f'image_{counter}'
        name = sanitize_filename(name)
        dest = images_root / name
        if dest.exists():
            stem = dest.stem
            suff = dest.suffix
            dest = images_root / f"{stem}_{counter}{suff}"
        try:
            saved = download_url(url, dest, session=session)
        except Exception:
            return m.group(0)
        rel = os.path.relpath(saved, md_path.parent).replace('\\', '/')
        seen[url] = rel
        counter += 1
        return m.group(0).replace(url, rel)

    text3 = IMG_HTML_RE.sub(replace_html, text2)

    # backup original
    if backup:
        bak = md_path.with_suffix(md_path.suffix + '.bak')
        if not bak.exists():
            md_path.replace(bak)
            # write transformed content to original path
            Path(bak.parent / md_path.name).write_text(text3, encoding='utf-8')
        else:
            # .bak exists — overwrite original file
            Path(bak.parent / md_path.name).write_text(text3, encoding='utf-8')
    else:
        Path(md_path).write_text(text3, encoding='utf-8')

    return seen


