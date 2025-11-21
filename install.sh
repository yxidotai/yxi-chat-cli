#!/bin/sh
set -e

# 安装到 /usr/local/bin (需要sudo)
if [ "$(id -u)" != "0" ]; then
  echo "需要sudo权限安装到系统目录"
  exec sudo "$0" "$@"
fi

# 创建安装目录
INSTALL_DIR="/usr/local/bin"
BIN_NAME="yxi"

# 复制二进制文件
cp "bin/$BIN_NAME" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/$BIN_NAME"

# 创建配置目录
CONFIG_DIR="$HOME/.config/yxi"
mkdir -p "$CONFIG_DIR"

# 设置自动更新
cat > "$CONFIG_DIR/update.sh" << 'EOF'
#!/bin/sh
curl -sL yxi.ai/cli | sh
EOF
chmod +x "$CONFIG_DIR/update.sh"

echo "✓ 已安装到 $INSTALL_DIR/$BIN_NAME"
echo "✓ 配置目录: $CONFIG_DIR"