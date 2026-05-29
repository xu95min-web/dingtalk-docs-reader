# DingTalk 内部 API 清单（已知）

本 skill 用到的钉钉内部 API。**不是钉钉 Open API**，无文档，仅供参考。可能随钉钉版本变化。

## 目录树

### `GET /box/api/v2/dentry/list?dentryUuid=<UUID>`

列某文件夹下直接子节点（不递归）。

**响应结构**：
```json
{
  "status": 200,
  "isSuccess": true,
  "data": {
    "children": [
      {
        "dentryUuid": "...",
        "dentryKey": "...",
        "dentryType": "folder|file",
        "name": "...",
        "hasChildren": true,
        "dentryStatistic": {"childrenCount": 15},
        "docKey": "...",          // file 才有
        "creator": {...},
        "spaceId": "..."
      }
    ]
  }
}
```

本 skill 用法：递归调用拿完整树。

### `GET /box/api/v2/dentry/info?dentryUuid=<UUID>`

查节点元数据（深度、祖先链、权限）。

## 文档内容

### `GET /i/nodes/<dentryUuid>`

文档主页（HTML）。会渲染 iframe 加载实际内容。

### `GET /api/document/data?docKey=<KEY>`（POST 也行）

返回文档元数据 + OSS 数据 key。

**响应结构**：
```json
{
  "data": {
    "accessToken": "...",
    "documentContent": {
      "checkpoint": {
        "ossKey": "collab/cp/.../...",
        "content": "{\"sheets\":[...],\"sheetMap\":{...}}"  // 元数据JSON
      }
    }
  }
}
```

- `content` 包含 sheet 列表和 field 定义
- 真实行数据要再请求 OSS（用 ossKey + accessToken）

### `GET /nt/api/celldoc/<sheetId>/queryPrimary`

多维表格里的主字段单元格内容。

### `GET /nt/api/docs/preset`

文档初始化配置（权限/创建者等）。

## 鉴权

钉钉是 Cookie + OAuth challenge：
1. 登录 `login.dingtalk.com` 拿基础 cookie
2. 访问 `alidocs.dingtalk.com/i/nodes/<uuid>` 触发 OAuth challenge
3. 人工点"同意"完成授权
4. 拿到 alidocs 子域的 SSO 票据 cookie

之后所有 alidocs API 调用都用同一套 cookie。

**Key cookies**（钉钉域）：
- `_dd_s`, `_dd_l` 等基础 session
- `aliyun-ax-csrf-token` 防 CSRF
- `cna` 设备指纹
- 各种 `dingtalk_*` 业务 token

cookie TTL：
- 不勾「自动登录」：~7 天
- 勾「自动登录」：~30 天

## 风控规则（推测）

钉钉对自动化的检测：
- ❌ headless 模式直接拦
- ❌ 无 user-agent / 异常 user-agent 拦
- ❌ 高频访问（每秒 > 1 个文档）触发 captcha
- ⚠️ 异地 IP 突然访问大量文档触发 SSO 重验

本 skill 的应对：
- 强制 headed 模式（窗口塞屏幕外，用户无感）
- 标准 Chrome user-agent
- 默认 `sleep 0.5s` 每文档
- 复用 cookie，不每次重登

## 不要做的事

⚠️ 钉钉条款明令禁止：
- 大规模爬取非授权内容
- 商业化使用爬虫工具
- 攻击钉钉服务

本 skill 仅为**个人合法访问内容**的便利工具。请自重。
