# 首次设置指南

跑通需要 **5 步**，约 **10-15 分钟**。

## 步骤 1：装 Python + Playwright

```bash
# 检查 Python
python3 --version  # 需要 3.9+

# 装 Playwright + Chromium（约 150MB）
pip3 install playwright
python3 -m playwright install chromium
```

**推荐用 venv** 避免污染系统 Python：

```bash
python3 -m venv ~/.dingtalk-reader/venv
source ~/.dingtalk-reader/venv/bin/activate
pip install playwright
playwright install chromium
```

之后所有 `python3` 都要用这个 venv：
```bash
~/.dingtalk-reader/venv/bin/python3 ~/.claude/skills/dingtalk-reader/reader.py ...
```

## 步骤 2：跑 setup 弹出浏览器

```bash
python3 ~/.claude/skills/dingtalk-reader/reader.py --login
```

会弹出一个 Chromium 窗口（不是你日常 Chrome，是 Playwright 自带的独立浏览器）。

## 步骤 3：登录钉钉 + **务必勾选「自动登录」**

在弹出的 Chromium 里：

1. 扫码或手机号 + 密码登录
2. **底部找到 ☐ 「自动登录」 / 「30 天免登录」复选框，勾上！**
   - ⚠️ 不勾的话 cookie 7 天就过期，每周要重 setup 一次
3. 登录成功

## 步骤 4：完成 SSO challenge（重要！）

钉钉的企业账号要走 OAuth 授权流程。如果直接访问 `alidocs.dingtalk.com` 主页，**不会**触发授权 —— 必须打开一个**具体的圈子/知识库 URL**。

操作：

1. 在同一个 Chromium 里，地址栏粘贴你要访问的**目标圈子 URL**（例如：`https://alidocs.dingtalk.com/i/nodes/xxxx?cid=yyy&corpId=zzz`）
2. 钉钉会弹一个授权页（含「同意」按钮）
3. **点「同意」**
4. 浏览器自动跳到那篇文档，**看到文档内容**（不是空白/不是登录页/不是 404）

**这一步如果没做，后续 read 会返回 NEED_LOGIN。**

## 步骤 5：关闭浏览器 + 验证

1. 回到终端，按回车关闭 Chromium
2. 终端会打印 `保存了 N 个 cookies（其中 M 个钉钉域）`
3. 钉钉域 cookie 应该 ≥ 15 个，少于 10 个可能登录态不全

验证：

```bash
python3 ~/.claude/skills/dingtalk-reader/reader.py "<刚才那个目标 URL>"
```

应该输出文档内容（一两屏文字）。

如果返回 `[NEED_LOGIN]`：回到步骤 4 重做，**确保浏览器里真的看到文档内容**再关闭。

## 常见登录卡点

### Q1：勾不到「自动登录」
看下登录界面是不是太老版了。新版钉钉登录页一般在「扫码登录」下方有这个勾选。如果实在没有，cookie 默认 TTL 较短，但能用，只是每周要 setup 一次。

### Q2：扫码登录后跳到「绑定手机号」/「企业账号注册」
那是你这个钉钉账号还没绑到企业，先在手机钉钉里加入对应企业/组织，再回来登。

### Q3：「点击同意」后没跳回文档
- 可能授权页有多个步骤（同意 → 选择登录账号 → 确认），都点完
- 可能这个钉钉账号在 corpId 对应企业里没有访问该圈子的权限 —— 联系圈子管理员要权限

### Q4：浏览器一直转圈不显示文档
- 网络问题，等久一点
- 钉钉风控触发（频繁登录），等 10 分钟再试

## 完成后

下次访问就不用 setup 了，cookie 自动用。30 天后过期时再重新 setup。

可以开始：
- `read <url>` 抓单页
- `tree <uuid>` 列目录
- `bulk <uuid>` 批量抓
- `sync-wiki <uuid> --wiki-name xxx` 入 llm-wiki
