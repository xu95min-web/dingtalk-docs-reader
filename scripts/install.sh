#!/bin/bash
# install.sh - 一键安装：建 venv + 装 Playwright + Chromium + 链接命令
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$HOME/.dingtalk-reader"
VENV="$DATA_DIR/venv"

echo "=== DingTalk Reader 安装 ==="
echo "Skill 目录: $SKILL_DIR"
echo "数据目录: $DATA_DIR"
echo ""

# 1. 建数据目录
mkdir -p "$DATA_DIR/profile" "$DATA_DIR/cache"

# 2. 建 venv
if [ ! -d "$VENV" ]; then
    echo "[1/4] 创建 venv..."
    python3 -m venv "$VENV"
fi

# 3. 装 Playwright
echo "[2/4] 装 Playwright..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet playwright

# 4. 装 Chromium
echo "[3/4] 下载 Chromium（约 150MB，可能要几分钟）..."
"$VENV/bin/python" -m playwright install chromium

# 5. 链接短命令到 /usr/local/bin
echo "[4/4] 链接 ding-read 命令..."
if [ -w /usr/local/bin ]; then
    ln -sf "$SKILL_DIR/scripts/ding-read" /usr/local/bin/ding-read
    echo "  ✅ 现在可以全局用 'ding-read' 命令"
else
    echo "  ⚠️  /usr/local/bin 没权限，跳过"
    echo "  手动加到 PATH: export PATH=\"$SKILL_DIR/scripts:\$PATH\""
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "下一步：首次登录"
echo "  ding-read --login"
echo ""
echo "登录时记得："
echo "  1. 勾选「自动登录」"
echo "  2. 浏览器里手动访问一次目标圈子/知识库 URL，看到内容再关浏览器"
