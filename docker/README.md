# MCP Gateway Docker Deployment Guide

This guide covers how to deploy the MCP Gateway using Docker for both development and production environments.

## Quick Start

### Development Environment

```bash
# Build and start development environment
./docker/build.sh dev

# View logs
./docker/build.sh logs

# Stop containers
./docker/build.sh stop
```

### Production Environment

```bash
# 1. Create production environment file
cp .env.production.example .env.production

# 2. Edit production settings
nano .env.production

# 3. Build and start production environment
./docker/build.sh prod
```

## Files Overview

- `Dockerfile` - Multi-stage Docker build for MCP Gateway
- `docker-compose.yml` - Development environment configuration
- `docker-compose.prod.yml` - Production environment configuration
- `nginx.conf` - Nginx reverse proxy configuration
- `build.sh` - Build and deployment script
- `.dockerignore` - Files excluded from Docker build

## Environment Configuration

### Development (.env)

The development environment uses your existing `.env` file or creates one from `.env.example`.

### Production (.env.production)

Create a production environment file with the following key settings:

```env
# Security (REQUIRED)
API_KEY=your-secure-api-key-here
ALLOWED_ORIGINS=["https://your-domain.com"]

# MCP Servers
MCP_SERVERS=[
  {
    "name": "context7",
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp@latest"],
    "env": {
      "UPSTASH_REDIS_REST_URL": "your-redis-url",
      "UPSTASH_REDIS_REST_TOKEN": "your-redis-token"
    }
  }
]

# Third-party services
BRAVE_API_KEY=your-brave-api-key
GITHUB_PERSONAL_ACCESS_TOKEN=your-github-token
```

## Docker Images

### Base Image: `python:3.11-slim`

The Dockerfile uses a multi-stage build:
- **Builder stage**: Installs build dependencies and Python packages
- **Production stage**: Creates lean production image with runtime dependencies

### Features

- ✅ **Multi-stage build** for smaller production images
- ✅ **Non-root user** for security
- ✅ **Node.js support** for MCP servers that need npm packages
- ✅ **Health checks** built-in
- ✅ **Persistent volumes** for logs and data
- ✅ **Proper signal handling** for graceful shutdown

## Production Deployment

### Prerequisites

1. **Docker** and **Docker Compose** installed
2. **Production environment file** (`.env.production`)
3. **SSL certificates** (if using HTTPS)

### Step-by-Step Deployment

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mcp-gateway
   ```

2. **Configure production environment**
   ```bash
   cp .env.production.example .env.production
   nano .env.production
   ```

3. **Build and deploy**
   ```bash
   ./docker/build.sh prod
   ```

4. **Verify deployment**
   ```bash
   # Check container status
   docker-compose -f docker/docker-compose.prod.yml ps
   
   # Check logs
   docker-compose -f docker/docker-compose.prod.yml logs -f
   
   # Test health endpoint
   curl http://localhost:8020/api/v1/health
   ```

## SSL/HTTPS Configuration

### Option 1: Nginx Reverse Proxy (Recommended)

The production compose includes an Nginx reverse proxy:

1. **Obtain SSL certificates**
   ```bash
   # Using Let's Encrypt
   sudo certbot certonly --standalone -d your-domain.com
   
   # Copy certificates
   sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem docker/ssl/cert.pem
   sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem docker/ssl/key.pem
   ```

2. **Update nginx.conf**
   ```nginx
   # Uncomment HTTPS sections in docker/nginx.conf
   listen 443 ssl http2;
   ssl_certificate /etc/nginx/ssl/cert.pem;
   ssl_certificate_key /etc/nginx/ssl/key.pem;
   ```

3. **Enable nginx in docker-compose**
   ```yaml
   # Uncomment nginx service in docker-compose.prod.yml
   ```

### Option 2: External Load Balancer

Use an external load balancer (AWS ALB, CloudFlare, etc.) and run the gateway with HTTP only.

## Monitoring and Logging

### Health Checks

- **Container health**: `docker-compose ps`
- **Application health**: `curl http://localhost:8020/api/v1/health`
- **Nginx health**: `curl http://localhost/health`

### Logs

```bash
# View all logs
docker-compose -f docker/docker-compose.prod.yml logs -f

# View specific service logs
docker-compose -f docker/docker-compose.prod.yml logs -f mcp-gateway
docker-compose -f docker/docker-compose.prod.yml logs -f nginx

# View logs with timestamps
docker-compose -f docker/docker-compose.prod.yml logs -f -t
```

### Log Rotation

Logs are automatically rotated:
- **Max size**: 50MB per file
- **Max files**: 5 files
- **Total retention**: ~250MB per service

## Scaling and Performance

### Resource Limits

Production containers have resource limits:
- **CPU**: 2 cores max, 0.5 cores reserved
- **Memory**: 1GB max, 512MB reserved

### Scaling

```bash
# Scale to multiple instances
docker-compose -f docker/docker-compose.prod.yml up -d --scale mcp-gateway=3

# Use load balancer to distribute traffic
```

## Security Best Practices

### Container Security

- ✅ **Non-root user** (`mcpgateway:1000`)
- ✅ **Read-only root filesystem** where possible
- ✅ **Minimal base image** (`python:3.11-slim`)
- ✅ **No unnecessary packages** in production image

### Network Security

- ✅ **Internal network** for container communication
- ✅ **Rate limiting** via Nginx
- ✅ **Security headers** configured
- ✅ **API key authentication** required

### Environment Security

- ✅ **Secrets in environment files** (not in code)
- ✅ **Restricted file permissions** on `.env.production`
- ✅ **HTTPS/TLS encryption** in production

## Troubleshooting

### Common Issues

1. **Container won't start**
   ```bash
   # Check logs
   docker-compose -f docker/docker-compose.prod.yml logs mcp-gateway
   
   # Check environment file
   cat .env.production
   ```

2. **Health check failing**
   ```bash
   # Test health endpoint directly
   docker exec mcp-gateway-prod curl http://localhost:8020/api/v1/health
   ```

3. **MCP servers not connecting**
   ```bash
   # Check MCP server logs
   docker-compose -f docker/docker-compose.prod.yml logs mcp-gateway | grep -i "mcp\|server"
   ```

4. **Permission issues**
   ```bash
   # Check file permissions
   docker exec mcp-gateway-prod ls -la /app/
   ```

### Debug Mode

```bash
# Run with debug logging
LOG_LEVEL=DEBUG docker-compose -f docker/docker-compose.prod.yml up -d

# View debug logs
docker-compose -f docker/docker-compose.prod.yml logs -f mcp-gateway
```

## Maintenance

### Updates

```bash
# Update to latest version
git pull origin main

# Rebuild and redeploy
./docker/build.sh prod
```

### Backup

```bash
# Backup persistent data
docker run --rm -v mcp-gateway-prod_gateway-data:/data alpine tar czf - /data > gateway-backup.tar.gz
```

### Cleanup

```bash
# Clean up old containers and images
./docker/build.sh clean

# Remove unused Docker resources
docker system prune -a
```

## Support

For issues and questions:
- Check the logs first
- Review the environment configuration
- Ensure all required services are running
- Verify network connectivity between containers

## Advanced Configuration

### Custom MCP Servers

Add custom MCP servers to your production environment:

```json
{
  "name": "custom-server",
  "command": "python",
  "args": ["-m", "your_custom_mcp_server"],
  "env": {
    "CUSTOM_ENV_VAR": "value"
  }
}
```

### Database Persistence

Enable database persistence:

```env
DATABASE_URL=postgresql://user:password@db-host:5432/mcpgateway
```

### Monitoring Integration

Integrate with monitoring systems:
- **Prometheus**: Metrics endpoint at `/metrics`
- **Grafana**: Dashboard templates available
- **ELK Stack**: Structured JSON logging 