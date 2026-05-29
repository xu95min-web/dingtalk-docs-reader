---
name: dingtalk-reader
description: |
  Read DingTalk Docs (alidocs.dingtalk.com), 圈子 (DingTalk Circles), 多维表格 (notable spreadsheets),
  and 知识库 (wiki) from the command line using a persistent Chromium profile. Use for: extracting
  content from DingTalk docs you have access to; bulk-syncing 圈子 articles into a local knowledge
  base; listing directory trees of DingTalk knowledge bases; any phrase like
  "钉钉文档抓取", "钉钉读取", "ding-read", "圈子内容同步", "alidocs 抓取", "钉钉知识库导出",
  "把钉钉文档同步到 wiki".
  Subcommands: setup, read, tree, bulk, sync-wiki, doctor.
  Do NOT use for: building DingTalk chatbots, sending messages to DingTalk groups (use DingTalk
  webhook), or anything that needs DingTalk Open API (this skill uses browser automation only).
  Only works for content the user has legitimate access to (own docs, joined circles, paid 圈子).
argument-hint: "setup | read <url> | tree <root_uuid> | bulk <folder_uuid> [out_dir] | sync-wiki <folder_uuid> | doctor"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
  - Grep
  - Glob
---

# DingTalk Reader Skill

读取钉钉文档 / 多维表格 / 圈子内容到本地，并可一键同步到 llm-wiki。

数据存放在 `~/.dingtalk-reader/`：
- `profile/` — 持久化的 Chromium profile（含登录态）
- `cache/` — 抓取的内容缓存

skill 目录 SKILL_DIR：`~/.claude/skills/dingtalk-reader/`

## 命令解析

| 用户说 | 子命令 |
|--------|--------|
| `setup`, `配置`, `初始化`, `首次登录`, `登钉钉` | setup |
| `read <url>`, `抓 <url>`, `读这个钉钉文档`, `<url>` | read |
| `tree <uuid>`, `列目录`, `看文件夹结构` | tree |
| `bulk <uuid>`, `批量抓 <文件夹>`, `把这个文件夹全抓了` | bulk |
| `sync-wiki <uuid>`, `同步到 wiki`, `入库` | sync-wiki |
| `doctor`, `诊断`, `挂了`, `没反应`, `跳到登录页` | doctor |

## Runtime detection

执行任何子命令前：
1. 检查 `~/.dingtalk-reader/profile/` 是否存在且非空。
2. 不存在 → 自动跳到 `setup`。
3. 存在 → 继续执行。

如果调用 `read` 但返回了登录页 HTML（含 `oauth2/challenge` 或 `login.dingtalk.com`）→ 提示用户 cookie 过期，运行 `setup` 重新登录。

## 子命令

### `setup`

引导用户**首次登录**钉钉，并完成一次 SSO 同意（点"同意"按钮）。

步骤：

1. 告诉用户 Python 和 Playwright 要装一次：
   ```bash
   pip3 install playwright && python3 -m playwright install chromium
   ```
   或用 venv（推荐）：
   ```bash
   python3 -m venv ~/.dingtalk-reader/venv
   source ~/.dingtalk-reader/venv/bin/activate
   pip install playwright && playwright install chromium
   ```

2. 调用：
   ```bash
   python3 SKILL_DIR/reader.py --login
   ```
   会弹出 Chromium，请用户：
   - 扫码或账号密码登录钉钉
   - **务必勾选「自动登录」**（cookie 30 天 TTL，否则 7 天就过期）
   - 浏览器里**手动访问一次目标圈子/知识库 URL**，完成 OAuth challenge（点"同意"按钮）
   - 看到文档内容后按终端回车关闭浏览器

3. 验证：跑一次 `read <url>` 看是否能拿到内容，能就 setup 成功。

详细引导见 `SKILL_DIR/references/setup-guide.md`。

### `read <url>`

抓取单个 URL 内容。

```bash
python3 SKILL_DIR/reader.py "<url>"
```

输出：MAIN PAGE 文本 + 所有 iframe 文本 + 截获的 JSON XHR（如果是多维表格）。

参数：
- `--text` 仅抓 DOM 文本
- `--api` 仅抓 XHR JSON
- `--wait <ms>` 增加等待时间（默认 20000ms）
- `--headed` 显示浏览器窗口（调试用，默认是屏幕外不可见）

### `tree <root_uuid>`

递归列出钉钉某文件夹下的目录树。

```bash
python3 SKILL_DIR/reader.py --tree <root_uuid> [--max-depth 10]
```

输出：JSON 树状结构（每个节点含 name/type/uuid/dentryKey/depth）。

获取 root_uuid：打开钉钉文件夹页面 → 抓 `/box/api/v2/dentry/list?dentryUuid=...` 这个请求里的 dentryUuid。或者把根 URL 给 reader，它会自动解析。

### `bulk <folder_uuid> [out_dir]`

批量抓某文件夹下所有 .adoc 文档到本地。

```bash
python3 SKILL_DIR/reader.py --bulk <folder_uuid> --out ~/dingtalk-export/
```

输出：每篇一个 `.txt` 文件，命名格式 `doc_<uuid>_<safe_name>.txt`。

默认 out_dir：`~/.dingtalk-reader/cache/<timestamp>/`

### `sync-wiki <folder_uuid>`

`bulk` 的升级版：抓完直接进 `~/llm-wiki/`（按 llm-wiki skill 的格式）。

```bash
python3 SKILL_DIR/reader.py --sync-wiki <folder_uuid> --wiki-name <kb-name>
```

会创建：
- `~/llm-wiki/raw/<kb-name>/` 原文
- `~/llm-wiki/wiki/<kb-name>/docs/` 文档页（带 frontmatter）

之后用户可以通过 llm-wiki skill 进一步整理章节/实体/索引。

### `doctor`

诊断常见问题。检查项：

1. `~/.dingtalk-reader/profile/` 是否存在且非空
2. `playwright` 是否能 import
3. `Chromium` 是否安装
4. 实测访问 `https://alidocs.dingtalk.com/` 是否返回登录页

输出诊断报告 + 修复建议。

常见问题 + 修复见 `SKILL_DIR/references/troubleshooting.md`。

## 已知限制

1. **钉钉风控拦 headless**：必须用 headed 模式（窗口塞屏幕外用户看不到）
2. **OAuth SSO 必须人工点"同意"一次**：第一次登录无法绕过
3. **多维表格 ≥ 1000 行需要滚动加载**：单次抓取可能不全
4. **钉钉前端升级可能破坏 selector**：定期更新
5. **法律**：仅限抓取你**有合法访问权**的内容（自己的文档/加入的圈子/付费订阅的内容）。不要用于盗取付费内容、爬取他人非公开数据

## 注意事项

- 操作前必须 `setup`，否则无登录态
- cookie 过期会被悄悄跳登录页，要靠 `doctor` 或 `read` 失败兜底检测
- skill 用户没看到弹窗 = 正常（窗口塞屏幕外）
- 建议先 `read <一个 URL>` 验证再 `bulk`
