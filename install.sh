#!/bin/sh
set -e

# 安装到 /usr/local/bin (需要sudo)
if [ "$(id -u)" != "0" ]; then
  if ! command -v sudo >/dev/null 2>&1; then
    echo "需要root权限或sudo支持才能安装" >&2
    exit 1
  fi
  echo "需要sudo权限安装到系统目录"
  exec sudo ORIGINAL_USER_HOME="$HOME" "$0" "$@"
fi

# 解析真正的用户家目录，确保配置写入非root账户
if [ -z "$ORIGINAL_USER_HOME" ] && [ -n "$SUDO_USER" ]; then
  ORIGINAL_USER_HOME=$(eval echo "~$SUDO_USER")
fi
USER_HOME="${ORIGINAL_USER_HOME:-$HOME}"

# 创建安装目录
INSTALL_DIR="/usr/local/bin"
BIN_NAME="yxi"

# 复制二进制文件
cp "bin/$BIN_NAME" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/$BIN_NAME"

# 创建配置目录
CONFIG_DIR="$USER_HOME/.config/yxi"
mkdir -p "$CONFIG_DIR"

# 设置自动更新脚本，默认从 GitHub Raw 获取最新 install.sh
cat > "$CONFIG_DIR/update.sh" << 'EOF'
#!/bin/sh
set -e

curl -sL yxi.ai/install.sh | sh
EOF
chmod +x "$CONFIG_DIR/update.sh"

echo "✓ 已安装到 $INSTALL_DIR/$BIN_NAME"
echo "✓ 配置目录: $CONFIG_DIR"
echo "✓ 可使用 'yxi update' 获取最新版本"