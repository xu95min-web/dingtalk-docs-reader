#!/usr/bin/env python3
"""DingTalk Reader - Browser-automation bridge to read alidocs.dingtalk.com content.

用法（详见 SKILL.md）:
    reader.py --login                          # 首次登录
    reader.py "<URL>"                          # 抓单页
    reader.py --tree <root_uuid>               # 列目录树
    reader.py --bulk <folder_uuid> [--out DIR] # 批量抓
    reader.py --sync-wiki <folder_uuid> --wiki-name <name>  # 一键入 llm-wiki
    reader.py --doctor                         # 诊断
"""
import sys
import os
import time
import json
import re
import argparse
from pathlib import Path

HOME = Path.home()
DATA_DIR = HOME / '.dingtalk-reader'
PROFILE_DIR = DATA_DIR / 'profile'
CACHE_DIR = DATA_DIR / 'cache'
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DATA_API_KEYWORDS = ['notable', 'listRecord', 'getRecord', 'view', 'sheet', 'fields', 'queryRecord', 'document/data']
INVALID_DOMAINS = ['alicdn', 'analytics', 'aliyun', 'g.alicdn']


def _safe_name(s):
    s = re.sub(r'\.adoc$', '', s)
    s = re.sub(r'[/\\:*?"<>|]', '_', s)
    return s.strip()[:100]


def _launch_ctx(p, visible=False):
    args = []
    if not visible:
        args = ['--window-position=-3000,-3000', '--window-size=1280,800']
    return p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=False,  # 钉钉拦 headless 必须 headed
        viewport={'width': 1440, 'height': 900},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        locale='zh-CN',
        args=args,
    )


# ============ login ============
def login_flow():
    from playwright.sync_api import sync_playwright
    print('打开 Chromium。请：')
    print('  1. 扫码 / 账号密码登录')
    print('  2. ⭐ 务必勾选「自动登录」 / 「30 天免登」')
    print('  3. 浏览器里手动打开一次目标圈子/知识库 URL，看到内容（完成 SSO challenge）')
    print('  4. 看到内容后回这里按回车关闭浏览器')
    with sync_playwright() as p:
        ctx = _launch_ctx(p, visible=True)
        page = ctx.new_page()
        page.goto('https://login.dingtalk.com/', wait_until='domcontentloaded')
        input('\n[完成上述 4 步后按回车关闭浏览器]')
        cookies = ctx.cookies()
        ding = [c for c in cookies if 'dingtalk' in c['domain'] or 'alidocs' in c['domain']]
        print(f'保存了 {len(cookies)} 个 cookies（其中 {len(ding)} 个钉钉域）')
        if len(ding) < 10:
            print('⚠️  钉钉 cookies 偏少，可能登录态不全。建议重新走 setup')
        ctx.close()


# ============ read 单页 ============
def read_url(url, mode='auto', wait_ms=20000, visible=False):
    from playwright.sync_api import sync_playwright
    captured = []
    with sync_playwright() as p:
        ctx = _launch_ctx(p, visible=visible)
        try:
            page = ctx.new_page()

            def on_resp(r):
                try:
                    if 'json' not in r.headers.get('content-type', '').lower():
                        return
                    if not any(k.lower() in r.url.lower() for k in DATA_API_KEYWORDS):
                        return
                    if r.status >= 400:
                        return
                    captured.append({'url': r.url, 'body': r.json()})
                except Exception:
                    pass

            page.on('response', on_resp)
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            try:
                page.wait_for_load_state('networkidle', timeout=wait_ms)
            except Exception:
                pass
            time.sleep(3)

            # 检测登录页
            if 'login.dingtalk.com' in page.url:
                return f'[NEED_LOGIN] 当前 profile 未登录或 SSO challenge 未完成。请运行 reader.py --login 重新登录。\n实际页面: {page.url}'

            chunks = []
            if mode in ('auto', 'api') and captured:
                useful = [c for c in captured
                          if isinstance(c['body'], dict) and len(json.dumps(c['body'])) > 100]
                if useful:
                    chunks.append(f'=== 截获 {len(useful)} 个数据 API 响应 ===')
                    for i, c in enumerate(useful):
                        chunks.append(f'\n--- API {i+1}: {c["url"][:120]} ---')
                        chunks.append(json.dumps(c['body'], ensure_ascii=False, indent=2)[:8000])

            if mode in ('auto', 'text'):
                try:
                    main_text = page.evaluate('() => document.body ? document.body.innerText : ""')
                    if main_text and main_text.strip():
                        chunks.append(f'\n=== MAIN ({page.url[:100]}) ===')
                        chunks.append(main_text[:8000])
                except Exception as e:
                    chunks.append(f'[main eval failed: {e}]')

                for i, fr in enumerate(page.frames):
                    if fr == page.main_frame:
                        continue
                    if any(d in fr.url for d in INVALID_DOMAINS):
                        continue
                    try:
                        fr_text = fr.evaluate('() => document.body ? document.body.innerText : ""')
                        if fr_text and fr_text.strip():
                            chunks.append(f'\n=== IFRAME {i} ({fr.url[:100]}) ===')
                            chunks.append(fr_text[:8000])
                    except Exception:
                        pass

            if not chunks:
                return '[空] 没抓到内容。可能 SSO 未通过 / 文档无权限 / 数据未加载'
            return '\n'.join(chunks)
        finally:
            ctx.close()


# ============ tree 递归列目录 ============
def list_tree(root_uuid, max_depth=10):
    from playwright.sync_api import sync_playwright

    def recurse(page, uuid, depth=0, results=None):
        if results is None:
            results = []
        if depth > max_depth:
            return results
        try:
            r = page.evaluate(f'''async () => {{
                const resp = await fetch('https://alidocs.dingtalk.com/box/api/v2/dentry/list?dentryUuid={uuid}', {{credentials:'include'}});
                return await resp.json();
            }}''')
            for c in (r.get('data') or {}).get('children', []):
                entry = {
                    'depth': depth,
                    'name': c.get('name'),
                    'type': c.get('dentryType'),
                    'uuid': c.get('dentryUuid'),
                    'dentryKey': c.get('dentryKey'),
                    'parent_uuid': uuid,
                    'has_children': c.get('hasChildren', False),
                }
                results.append(entry)
                if entry['type'] == 'folder' and entry['has_children']:
                    recurse(page, entry['uuid'], depth + 1, results)
            time.sleep(0.3)
        except Exception as e:
            print(f'[err depth={depth}] {e}', file=sys.stderr)
        return results

    with sync_playwright() as p:
        ctx = _launch_ctx(p)
        try:
            page = ctx.new_page()
            page.goto('https://alidocs.dingtalk.com/', wait_until='domcontentloaded')
            time.sleep(2)
            return recurse(page, root_uuid)
        finally:
            ctx.close()


# ============ bulk 批量抓 ============
def bulk_fetch(folder_uuid, out_dir):
    from playwright.sync_api import sync_playwright
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    print(f'[1/2] 列目录树...', flush=True)
    tree = list_tree(folder_uuid)
    files = [t for t in tree if t['type'] == 'file']
    print(f'共 {len(files)} 篇要抓\n', flush=True)

    print(f'[2/2] 抓取中...', flush=True)
    ok = skip = fail = 0
    with sync_playwright() as p:
        ctx = _launch_ctx(p)
        page = ctx.new_page()
        page.goto('https://alidocs.dingtalk.com/', wait_until='domcontentloaded')
        time.sleep(2)
        for i, d in enumerate(files, 1):
            name, uuid = d['name'], d['uuid']
            out_file = out / f'doc_{uuid}_{_safe_name(name)}.txt'
            if out_file.exists() and out_file.stat().st_size > 200:
                skip += 1
                print(f'  [{i}/{len(files)}] SKIP {name}', flush=True)
                continue
            try:
                url = f'https://alidocs.dingtalk.com/i/nodes/{uuid}'
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                try:
                    page.wait_for_load_state('networkidle', timeout=15000)
                except Exception:
                    pass
                time.sleep(2.5)
                chunks = []
                try:
                    chunks.append(page.evaluate('() => document.body ? document.body.innerText : ""'))
                except Exception:
                    pass
                for fr in page.frames:
                    if fr == page.main_frame:
                        continue
                    if any(x in fr.url for x in INVALID_DOMAINS):
                        continue
                    try:
                        t = fr.evaluate('() => document.body ? document.body.innerText : ""')
                        if t and len(t) > 100:
                            chunks.append(f'\n=== iframe ===\n{t}')
                    except Exception:
                        pass
                content = '\n'.join(chunks)
                if len(content) < 100:
                    fail += 1
                    print(f'  [{i}/{len(files)}] FAIL(empty) {name}', flush=True)
                    continue
                with open(out_file, 'w') as f:
                    f.write(f'# {name}\nUUID: {uuid}\nURL: {url}\n\n{content}')
                ok += 1
                print(f'  [{i}/{len(files)}] OK {name} ({len(content)}b)', flush=True)
            except Exception as e:
                fail += 1
                print(f'  [{i}/{len(files)}] FAIL {name}: {e}', flush=True)
            time.sleep(0.5)
        ctx.close()
    print(f'\n=== DONE: OK={ok} SKIP={skip} FAIL={fail} ===  输出: {out}', flush=True)
    return {'ok': ok, 'skip': skip, 'fail': fail, 'out_dir': str(out), 'tree': tree}


# ============ sync-wiki 一键入 llm-wiki ============
def sync_to_wiki(folder_uuid, wiki_name):
    wiki_base = HOME / 'llm-wiki'
    if not wiki_base.exists():
        print(f'[ERR] {wiki_base} 不存在。请先 init llm-wiki', file=sys.stderr)
        return
    raw_dir = wiki_base / 'raw' / wiki_name
    docs_dir = wiki_base / 'wiki' / wiki_name / 'docs'
    raw_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    bulk_fetch(folder_uuid, raw_dir)

    print(f'\n[wiki] 生成 wiki 文档页...', flush=True)
    n = 0
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.startswith('doc_'):
            continue
        with open(raw_dir / fn) as f:
            content = f.read()
        name_m = re.search(r'^# (.+?)$', content, re.MULTILINE)
        uuid_m = re.search(r'^UUID: (\S+)$', content, re.MULTILINE)
        url_m = re.search(r'^URL: (\S+)$', content, re.MULTILINE)
        if not name_m:
            continue
        name = name_m.group(1).replace('.adoc', '').strip()
        uuid = uuid_m.group(1) if uuid_m else ''
        url = url_m.group(1) if url_m else ''
        body = content[url_m.end():].strip() if url_m else content

        slug = _safe_name(name)
        out = docs_dir / f'{slug}.md'
        out.write_text(f'''---
name: {slug}
description: 来自 {wiki_name} 的 {name}
metadata:
  type: source-summary
  source_uuid: {uuid}
  source_url: {url}
tags: [source-summary, {wiki_name}]
---

# {name}

> 来源：[钉钉原文]({url})

{body}
''')
        n += 1
    print(f'[wiki] 生成了 {n} 个文档页 → {docs_dir}', flush=True)
    print(f'\n下一步建议：在 Claude Code 里说「按 llm-wiki 风格给 {wiki_name} 建索引和章节页」', flush=True)


# ============ doctor 诊断 ============
def doctor():
    print('=== DingTalk Reader Doctor ===\n')

    # 1. profile
    if not PROFILE_DIR.exists() or not any(PROFILE_DIR.iterdir()):
        print('❌ Profile 不存在或为空')
        print('   修复：reader.py --login')
        return
    print('✅ Profile 存在')

    # 2. playwright import
    try:
        import playwright
        print(f'✅ Playwright {playwright.__version__} 已安装')
    except ImportError:
        print('❌ Playwright 未安装')
        print('   修复：pip3 install playwright && python3 -m playwright install chromium')
        return

    # 3. chromium
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            ctx = _launch_ctx(p)
            ctx.close()
        print('✅ Chromium 能启动')
    except Exception as e:
        print(f'❌ Chromium 启动失败: {e}')
        return

    # 4. cookies
    try:
        with sync_playwright() as p:
            ctx = _launch_ctx(p)
            cookies = ctx.cookies()
            ding = [c for c in cookies if 'dingtalk' in c['domain'] or 'alidocs' in c['domain']]
            print(f'✅ Cookies: 总 {len(cookies)} / 钉钉域 {len(ding)}')
            if len(ding) < 10:
                print('   ⚠️  钉钉 cookies 偏少。建议重新 setup')
            ctx.close()
    except Exception as e:
        print(f'❌ 读 cookies 失败: {e}')
        return

    # 5. 实测一个 URL（中性的钉钉主页）
    try:
        with sync_playwright() as p:
            ctx = _launch_ctx(p)
            page = ctx.new_page()
            page.goto('https://alidocs.dingtalk.com/', wait_until='domcontentloaded', timeout=15000)
            time.sleep(3)
            if 'login' in page.url.lower():
                print(f'⚠️  访问 alidocs 被跳到登录页（cookie 过期？）')
                print('   修复：reader.py --login')
            else:
                print(f'✅ 能访问 alidocs（当前 URL: {page.url[:80]}）')
            ctx.close()
    except Exception as e:
        print(f'❌ 访问 alidocs 失败: {e}')

    print('\n诊断完成。')


# ============ main ============
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url', nargs='?', help='URL (read 模式)')
    parser.add_argument('--login', action='store_true')
    parser.add_argument('--tree', metavar='UUID')
    parser.add_argument('--bulk', metavar='UUID')
    parser.add_argument('--sync-wiki', metavar='UUID')
    parser.add_argument('--wiki-name', metavar='NAME', help='与 --sync-wiki 配合用')
    parser.add_argument('--out', metavar='DIR', help='与 --bulk 配合用，默认 ~/.dingtalk-reader/cache/<ts>/')
    parser.add_argument('--max-depth', type=int, default=10)
    parser.add_argument('--text', action='store_true', help='read 模式: 仅抓 DOM 文本')
    parser.add_argument('--api', action='store_true', help='read 模式: 仅抓 XHR JSON')
    parser.add_argument('--headed', action='store_true', help='调试: 显示浏览器')
    parser.add_argument('--wait', type=int, default=20000)
    parser.add_argument('--doctor', action='store_true')
    args = parser.parse_args()

    if args.doctor:
        doctor()
        return

    if args.login:
        login_flow()
        return

    if args.tree:
        tree = list_tree(args.tree, max_depth=args.max_depth)
        print(json.dumps(tree, ensure_ascii=False, indent=2))
        return

    if args.bulk:
        from datetime import datetime
        out = args.out or str(CACHE_DIR / datetime.now().strftime('%Y%m%d_%H%M%S'))
        bulk_fetch(args.bulk, out)
        return

    if args.sync_wiki:
        if not args.wiki_name:
            print('Error: --sync-wiki 必须配合 --wiki-name <name>', file=sys.stderr)
            sys.exit(1)
        sync_to_wiki(args.sync_wiki, args.wiki_name)
        return

    if not args.url:
        parser.print_help()
        sys.exit(1)

    mode = 'auto'
    if args.text:
        mode = 'text'
    elif args.api:
        mode = 'api'
    print(read_url(args.url, mode=mode, wait_ms=args.wait, visible=args.headed))


if __name__ == '__main__':
    main()
