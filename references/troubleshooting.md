# 故障排查

先跑 `reader.py --doctor` 自动诊断。

## 常见问题

### 1. `[NEED_LOGIN] 当前 profile 未登录或 SSO challenge 未完成`

**原因**：
- 没跑过 `--login`
- 跑了 `--login` 但没勾「自动登录」，cookie 过期
- 跑了 `--login` 但没在浏览器里完成 SSO challenge（点"同意"）

**修复**：
1. 跑 `reader.py --doctor` 看 cookie 数量
2. 钉钉域 cookie < 10 → 重新 `reader.py --login`
3. **关键**：登录后在 Chromium 里**手动访问一次目标文档 URL**，看到内容再关浏览器

### 2. 文档抓回来是空的 / 只有目录树噪音

**原因**：
- 文档是 .adoc 富文本：内容在 iframe 里，可能要等更久
- 文档是 .notable 多维表格：数据在 canvas 上，要靠 XHR 抓

**修复**：
- 加 `--wait 30000` 等更长
- 用 `--api` 模式专门抓 XHR
- 抓不到再换 `--text` 模式

```bash
reader.py "<url>" --wait 30000      # 等 30 秒
reader.py "<url>" --api             # 只抓 JSON XHR
reader.py "<url>" --text            # 只抓 DOM 文本
```

### 3. 弹出来浏览器后什么都没发生

**原因**：脚本崩在 launch_persistent_context

**修复**：
1. 检查 Chromium 装没装：`python3 -m playwright install chromium`
2. 检查 profile 目录权限：`ls -la ~/.dingtalk-reader/profile`
3. 试着删 profile 重 login（保留数据备份）：
   ```bash
   mv ~/.dingtalk-reader/profile ~/.dingtalk-reader/profile.bak
   reader.py --login
   ```

### 4. 钉钉风控拦截（headless detected / 频繁访问）

**症状**：
- 弹出验证码 / 滑块
- 直接被踢到登录页
- API 返回 403

**修复**：
- 减慢 bulk 频率（脚本默认 sleep 0.5s，可改 1-2s）
- 切换网络（钉钉对部分 IP 段更敏感）
- 等 30 分钟再试
- 不要 24/7 后台跑，按需用

### 5. 多维表格只抓到前 N 行

**原因**：钉钉 notable 默认分页加载（每次 50-200 行），不滚动不加载

**修复**：当前 v1 还没实现滚动加载。临时方案：
- 在钉钉里**手动**改视图为"按筛选条件 < 200 行"
- 或分次按 column 筛选抓
- 后续版本会加 `--scroll` 参数

### 6. `--bulk` 跑到一半挂了

**原因**：网络抖 / Chromium 崩 / 钉钉风控

**修复**：直接重跑同样的 `--bulk` 命令，已抓的会 SKIP（按文件名+大小判断）

```bash
reader.py --bulk <uuid> --out ~/Downloads/export/
# 中断后再跑同样命令，自动续传
```

### 7. `--sync-wiki` 报 `llm-wiki 不存在`

**原因**：你电脑没装 llm-wiki

**修复**：
```bash
mkdir -p ~/llm-wiki/raw ~/llm-wiki/wiki
echo "# Wiki 索引" > ~/llm-wiki/wiki/index.md
echo "# 操作日志" > ~/llm-wiki/wiki/log.md
```

或装 llm-wiki skill。

### 8. ARM Mac / M1/M2/M3 兼容

理论支持，没系统测过。如果 Chromium 起不来：

```bash
arch -arm64 pip install playwright
arch -arm64 playwright install chromium
```

## 调试

加 `--headed` 显示浏览器窗口看实际发生什么：

```bash
reader.py "<url>" --headed --wait 60000
```

会弹出 1280x800 的 Chromium，你可以看到加载过程。等 60 秒后自动关闭。

## 完全重置

```bash
rm -rf ~/.dingtalk-reader/profile
reader.py --login
```

会清掉登录态，重新走一遍。
