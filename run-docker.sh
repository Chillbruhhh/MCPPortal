#!/bin/bash

# Dynamic Docker runner for MCP Portal
# This script automatically detects and mounts user MCP configuration directories

echo "🔍 Detecting MCP configuration directories..."
echo "Operating System: $(uname -s)"
echo "User Home: $HOME"
echo ""

# Stop and remove existing container if it exists
docker stop mcp-portal-container 2>/dev/null || true
docker rm mcp-portal-container 2>/dev/null || true

# Base Docker command
CMD="docker run -d -p 8020:8020 --name mcp-portal-container"

# Detect OS and set paths accordingly
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    # Windows paths
    CURSOR_PATH="$HOME/.cursor"
    VSCODE_PATH="$HOME/AppData/Roaming/Code/User"
    CLAUDE_PATH="$HOME/AppData/Roaming/Claude"
    WINDSURF_PATH="$HOME/.windsurf"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS paths
    CURSOR_PATH="$HOME/.cursor"
    VSCODE_PATH="$HOME/Library/Application Support/Code/User"
    CLAUDE_PATH="$HOME/Library/Application Support/Claude"
    WINDSURF_PATH="$HOME/.windsurf"
else
    # Linux paths
    CURSOR_PATH="$HOME/.cursor"
    VSCODE_PATH="$HOME/.config/Code/User"
    CLAUDE_PATH="$HOME/.config/claude"
    WINDSURF_PATH="$HOME/.windsurf"
fi

# Add volume mounts for existing directories
if [ -d "$CURSOR_PATH" ]; then
    CMD="$CMD -v \"$CURSOR_PATH:/root/.cursor\""
    echo "✓ Found Cursor config at: $CURSOR_PATH"
else
    echo "✗ No Cursor config found at: $CURSOR_PATH"
fi

if [ -d "$VSCODE_PATH" ]; then
    CMD="$CMD -v \"$VSCODE_PATH:/root/.vscode\""
    echo "✓ Found VS Code config at: $VSCODE_PATH"
else
    echo "✗ No VS Code config found at: $VSCODE_PATH"
fi

if [ -d "$CLAUDE_PATH" ]; then
    CMD="$CMD -v \"$CLAUDE_PATH:/root/.claude\""
    echo "✓ Found Claude config at: $CLAUDE_PATH"
else
    echo "✗ No Claude config found at: $CLAUDE_PATH"
fi

if [ -d "$WINDSURF_PATH" ]; then
    CMD="$CMD -v \"$WINDSURF_PATH:/root/.windsurf\""
    echo "✓ Found Windsurf config at: $WINDSURF_PATH"
else
    echo "✗ No Windsurf config found at: $WINDSURF_PATH"
fi

# Add the image name
CMD="$CMD mcp-gateway"

echo ""
echo "🚀 Starting MCP Portal container..."
echo "Command: $CMD"
echo ""

# Run the command
eval $CMD

if [ $? -eq 0 ]; then
    echo "✅ Container started successfully!"
    echo ""
    echo "🌐 MCP Portal is running at: http://localhost:8020"
    echo ""
    echo "📊 To view logs: docker logs mcp-portal-container"
    echo "🛑 To stop: docker stop mcp-portal-container"
else
    echo "❌ Failed to start container"
    exit 1
fi 