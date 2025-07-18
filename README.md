<div align="center">
  <img src="assets/logo.jpg" alt="MCP Portal Logo" width="768" height="514">
  
  # MCP Portal 🚀
  
  **The Ultimate Model Context Protocol Hub**
  
  Aggregate tools from multiple MCP servers into a unified portal with dynamic discovery and cross-platform Docker support.
</div>

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ Features

- **🔍 Dynamic MCP Discovery**: Automatically finds and integrates MCP servers from Cursor, VS Code, Claude Desktop, and more
- **🌐 Unified API**: Single endpoint for all your MCP tools and resources
- **🐳 Docker Ready**: Cross-platform containerization with automatic configuration mounting
- **⚡ Real-time Management**: Web UI for server management, tool exploration, and configuration editing
- **🔧 Cross-Platform**: Works on Windows, macOS, and Linux with intelligent command translation
- **📊 Monitoring**: Built-in logging, health checks, and performance metrics

## 🚀 Quick Start

### Local Development
```bash
# Clone and install
git clone https://github.com/Chillbruhhh/MCPPortal.git
cd mcp-portal
pip install -r requirements.txt

# Start the portal
python -m mcp_gateway.main

# Open web UI: http://localhost:8020
```

### Docker Deployment
```bash
# Build image
docker build -t mcp-portal -f docker/Dockerfile .

# Auto-detect and run with your MCPs
python run-docker.py
```

## 🎯 How It Works

MCP Portal automatically discovers MCP servers from your IDE configurations and aggregates them into a single, unified interface:

```mermaid
graph TB
    subgraph "🔍 Discovery Phase"
        A[Cursor IDE<br/>Configuration] --> D[Configuration Scanner]
        B[VS Code<br/>Settings] --> D
        C[Claude Desktop<br/>Config] --> D
        E[Other IDEs<br/>Config Files] --> D
    end
    
    subgraph "🚀 MCP Portal Core"
        D --> F[Server Discovery Engine]
        F --> G[Configuration Parser]
        G --> H[Server Registry]
        H --> I[Process Manager]
        I --> J[Tool Aggregator]
        J --> K[Unified API Server]
    end
    
    subgraph "📡 MCP Servers"
        direction LR
        S1[Search Engine<br/>MCP Server]
        S2[Database Tools<br/>MCP Server] 
        S3[Browser Control<br/>MCP Server]
        S4[File System<br/>MCP Server]
        S5[Web Scraping<br/>MCP Server]
        S6[Code Analysis<br/>MCP Server]
    end
    
    subgraph "🛠️ Aggregated Tools"
        direction LR
        T1[web_search]
        T2[database_query]
        T3[take_screenshot]
        T4[read_file]
        T5[scrape_website]
        T6[analyze_code]
    end
    
    subgraph "🎛️ Management Dashboard"
        K --> N[Web UI Dashboard<br/>Monitor & Control MCP Servers]
        N --> N1[Server Status Monitor]
        N --> N2[Tool Management]
        N --> N3[Configuration Editor]
        N --> N4[Real-time Logs]
    end
    
    subgraph "🌐 AI Agent Interface"
        K --> L[REST API<br/>Tool Endpoints]
        K --> M[WebSocket/SSE<br/>Real-time Events]
    end
    
    subgraph "🤖 AI Agents & Applications"
        L --> O[Claude Desktop<br/>AI Assistant]
        L --> P[ChatGPT<br/>AI Assistant]
        M --> Q[Custom AI Apps<br/>Autonomous Agents]
        L --> R[Development Tools<br/>AI-Powered IDEs]
        L --> S[Multi-Agent Systems<br/>Agent Frameworks]
    end
    
    I -.-> S1
    I -.-> S2
    I -.-> S3
    I -.-> S4
    I -.-> S5
    I -.-> S6
    
    J --> T1
    J --> T2
    J --> T3
    J --> T4
    J --> T5
    J --> T6
    

    
    subgraph "🔄 Workflow"
        direction TB
        W1[1. Scan IDE Configs] --> W2[2. Parse MCP Settings]
        W2 --> W3[3. Start MCP Servers]
        W3 --> W4[4. Aggregate Tools]
        W4 --> W5[5. Expose Unified API]
        W5 --> W6[6. AI Agents Call Tools]
        W6 --> W7[7. Return Results]
    end
    
    classDef discoveryStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#000
    classDef portalStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px,color:#000
    classDef serverStyle fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#000
    classDef toolStyle fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#000
    classDef dashboardStyle fill:#fff8e1,stroke:#ff8f00,stroke-width:2px,color:#000
    classDef interfaceStyle fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#000
    classDef aiStyle fill:#e1f5fe,stroke:#0288d1,stroke-width:3px,color:#000
    classDef workflowStyle fill:#f1f8e9,stroke:#689f38,stroke-width:2px,color:#000
    
    class A,B,C,D,E discoveryStyle
    class F,G,H,I,J,K portalStyle
    class S1,S2,S3,S4,S5,S6 serverStyle
    class T1,T2,T3,T4,T5,T6 toolStyle
    class N,N1,N2,N3,N4 dashboardStyle
    class L,M interfaceStyle
    class O,P,Q,R,S aiStyle
    class W1,W2,W3,W4,W5,W6,W7 workflowStyle
```

## 🛠️ Supported IDEs & MCP Sources

- **Cursor IDE** (`.cursor/mcp.json`)
- **VS Code** (`settings.json`)
- **Claude Desktop** (`claude_desktop_config.json`)
- **Windsurf** (`.windsurf/mcp_servers.json`)
- **Continue.dev** (`.continue/config.json`)
- **Custom configurations**

## 📋 API Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/` | GET | Web UI dashboard |
| `/api/v1/servers` | GET | List all MCP servers |
| `/api/v1/tools` | GET | List all aggregated tools |
| `/api/v1/resources` | GET | List all resources |
| `/api/v1/config` | GET/POST | Manage MCP configurations |
| `/api/v1/servers/refresh` | POST | Refresh server discovery |
| `/sse` | GET | Server-Sent Events for real-time updates |

## 🔧 Configuration

### Environment Variables
```bash
MCP_PORTAL_PORT=8020
MCP_PORTAL_HOST=0.0.0.0
MCP_PORTAL_LOG_LEVEL=INFO
```

### Manual Configuration
```json
{
  "mcp_servers": [
    {
      "name": "my-mcp-server",
      "command": "npx",
      "args": ["@my-org/mcp-server"],
      "env": {
        "API_KEY": "your-api-key"
      }
    }
  ]
}
```

## 🐳 Docker Production Deployment

### Using Docker Compose
```yaml
# docker-compose.yml
version: '3.8'
services:
  mcp-portal:
    build: .
    ports:
      - "8020:8020"
    volumes:
      - ~/.cursor:/root/.cursor:ro
      - ~/.vscode:/root/.vscode:ro
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - MCP_PORTAL_LOG_LEVEL=INFO
```

### Production Scripts
```bash
# Build and run production container
./docker/build.sh prod

# View logs
docker logs mcp-portal-container

# Stop
docker stop mcp-portal-container
```

## 📖 Usage Examples

### List Available Tools
```bash
curl http://localhost:8020/api/v1/tools
```

### Execute a Tool
```bash
curl -X POST http://localhost:8020/api/v1/tools/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "brave-search", "arguments": {"query": "MCP documentation"}}'
```

### Web UI Features
- **Server Management**: Enable/disable MCP servers
- **Tool Explorer**: Browse and test tools interactively
- **Configuration Editor**: Edit MCP configs with JSON validation
- **Real-time Monitoring**: Live server status and logs

## 🧪 Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=mcp_gateway tests/

# Test specific functionality
pytest tests/test_discovery.py -v
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Documentation**: [Full Documentation](docs/)
- **Docker Hub**: [mcp-portal](https://hub.docker.com/r/chillbruhhh/mcp-portal)
- **Issues**: [GitHub Issues](https://github.com/Chillbruhhh/MCPPortal/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Chillbruhhh/MCPPortal/discussions)

## 🎉 Acknowledgments

- [Model Context Protocol](https://github.com/modelcontextprotocol/protocol) for the foundational framework
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [Pydantic](https://docs.pydantic.dev/) for data validation
- All the amazing MCP server developers in the community

---

**Ready to unlock the full potential of your MCP ecosystem?** ⭐ Star this repo and get started with `python run-docker.py`!