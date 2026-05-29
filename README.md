# DingTalk Reader Skill

读取钉钉文档 / 多维表格 / 圈子内容到本地，可一键同步到 [llm-wiki](https://github.com/aaaaaaaaaaaa/llm-wiki)。

不用钉钉 Open API，不要管理员权限。基于 Playwright 复用浏览器登录态。

## 适用场景

- **加入了钉钉付费圈子**（如优联荟、各种行业知识库），想把内容**本地化备份**或喂给 LLM 做 RAG
- **公司内部 wiki 在钉钉**，想离线访问/搜索
- **多维表格 → 本地 JSON**：钉钉 notable 内容是 canvas 渲染的，普通爬虫拿不到，本 skill 通过监听 XHR 解决

## 不适用场景

- ❌ 抓你没访问权限的内容（违反钉钉条款）
- ❌ 实时同步（每次抓都要等浏览器加载，3 秒 / 文档）
- ❌ 大批量自动化（钉钉风控会触发，建议每次 < 200 篇 + 间隔 0.5 秒）

## 法律提醒

- ✅ 抓**你自己的**钉钉文档
- ✅ 抓**你已经加入的圈子/知识库**里的内容（你已经付费/被授权访问）
- ❌ 不要把抓来的付费圈子内容**公开分享**
- ❌ 不要把这个 skill **包装成商业产品**卖（钉钉法务大概率发函）

## 环境要求

- macOS / Linux / WSL
- Python 3.9+
- ~150MB（Chromium）

## 安装

```bash
# 1. 把这个目录放到 ~/.claude/skills/dingtalk-reader/
git clone <repo> ~/.claude/skills/dingtalk-reader

# 2. 装 Playwright + Chromium（推荐用 venv）
python3 -m venv ~/.dingtalk-reader/venv
source ~/.dingtalk-reader/venv/bin/activate
pip install playwright
playwright install chromium

# 3. 首次登录
python3 ~/.claude/skills/dingtalk-reader/reader.py --login
```

## 用法（在 Claude Code 里）

```
/dingtalk-reader setup           # 首次登录
/dingtalk-reader read <URL>      # 抓单篇
/dingtalk-reader tree <uuid>     # 列目录
/dingtalk-reader bulk <uuid>     # 批量抓某文件夹
/dingtalk-reader sync-wiki <uuid> --wiki-name my-kb  # 一键入 llm-wiki
/dingtalk-reader doctor          # 诊断
```

## 用法（直接命令行）

```bash
PY=python3  # 或 ~/.dingtalk-reader/venv/bin/python

$PY ~/.claude/skills/dingtalk-reader/reader.py --login
$PY ~/.claude/skills/dingtalk-reader/reader.py "https://alidocs.dingtalk.com/i/nodes/xxx"
$PY ~/.claude/skills/dingtalk-reader/reader.py --tree <root_uuid>
$PY ~/.claude/skills/dingtalk-reader/reader.py --bulk <folder_uuid> --out ~/Downloads/export/
$PY ~/.claude/skills/dingtalk-reader/reader.py --sync-wiki <folder_uuid> --wiki-name optical-knowledge
$PY ~/.claude/skills/dingtalk-reader/reader.py --doctor
```

## 实际效果

某优联荟用户的实战数据：
- 抓取一个含 14 章节 / 125 篇文档 / 760KB 的圈子，约 **30 分钟**
- 同步到 llm-wiki 后由 Claude 配合精读+索引：**$1 入库成本**，每次查询约 **$0.01-0.03**

## 工作原理

```
你（手动登录一次）
    ↓ cookie/SSO 票据存到 ~/.dingtalk-reader/profile/
Playwright 用同一个 profile 启动（headed + 窗口塞屏幕外）
    ↓ 通过 alidocs.dingtalk.com
读 JSON XHR + iframe innerText
    ↓
本地 .txt / .md
```

关键技术细节：
- **headed 模式**：钉钉风控会拦 headless
- **窗口塞 -3000,-3000**：用户看不到弹窗
- **OAuth SSO 一次性**：第一次必须人工点"同意"
- **XHR 抓包**：多维表格 canvas 渲染抓不到，必须截 `/api/document/data`
- **dentry tree API**：`/box/api/v2/dentry/list?dentryUuid=` 递归目录

## 故障排查

见 `references/troubleshooting.md`，或运行 `--doctor`。

## License

MIT
