#!/bin/bash

# MCP Gateway Docker Build Script
# This script builds and optionally deploys the MCP Gateway Docker container

set -e

# Configuration
IMAGE_NAME="mcp-portal"
IMAGE_TAG="latest"
CONTAINER_NAME="mcp-portal"
DOCKERFILE_PATH="docker/Dockerfile"
COMPOSE_FILE="docker/docker-compose.yml"
PROD_COMPOSE_FILE="docker/docker-compose.prod.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Build the Docker image
build_image() {
    log_info "Building MCP Gateway Docker image..."
    
    # Change to project root
    cd "$(dirname "$0")/.."
    
    # Build the image
    docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" -f "${DOCKERFILE_PATH}" .
    
    if [ $? -eq 0 ]; then
        log_info "Successfully built ${IMAGE_NAME}:${IMAGE_TAG}"
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
}

# Run development environment
run_dev() {
    log_info "Starting development environment..."
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        log_warn ".env file not found. Creating from .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
        else
            log_error ".env.example not found. Please create .env file manually."
            exit 1
        fi
    fi
    
    # Start with docker-compose
    docker-compose -f "${COMPOSE_FILE}" up -d
    
    log_info "Development environment started!"
    log_info "MCP Gateway is available at: http://localhost:8020"
    log_info "Use 'docker-compose -f ${COMPOSE_FILE} logs -f' to view logs"
}

# Run production environment
run_prod() {
    log_info "Starting production environment..."
    
    # Check if .env.production file exists
    if [ ! -f ".env.production" ]; then
        log_error ".env.production file not found. Please create it with production settings."
        exit 1
    fi
    
    # Start with production compose
    docker-compose -f "${PROD_COMPOSE_FILE}" up -d
    
    log_info "Production environment started!"
    log_info "MCP Gateway is available at: http://localhost:8020"
    log_info "Use 'docker-compose -f ${PROD_COMPOSE_FILE} logs -f' to view logs"
}

# Stop containers
stop() {
    log_info "Stopping MCP Gateway containers..."
    
    # Stop development environment
    if docker-compose -f "${COMPOSE_FILE}" ps -q > /dev/null 2>&1; then
        docker-compose -f "${COMPOSE_FILE}" down
    fi
    
    # Stop production environment
    if docker-compose -f "${PROD_COMPOSE_FILE}" ps -q > /dev/null 2>&1; then
        docker-compose -f "${PROD_COMPOSE_FILE}" down
    fi
    
    log_info "Containers stopped"
}

# Clean up
clean() {
    log_info "Cleaning up Docker resources..."
    
    # Stop containers
    stop
    
    # Remove image
    if docker images "${IMAGE_NAME}:${IMAGE_TAG}" -q > /dev/null 2>&1; then
        docker rmi "${IMAGE_NAME}:${IMAGE_TAG}"
    fi
    
    # Remove volumes (ask for confirmation)
    read -p "Remove persistent volumes? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker volume rm mcp-gateway-logs mcp-gateway-data 2>/dev/null || true
        docker volume rm mcp-gateway-prod-logs mcp-gateway-prod-data 2>/dev/null || true
        log_info "Volumes removed"
    fi
    
    log_info "Cleanup completed"
}

# Show help
show_help() {
    echo "MCP Gateway Docker Build Script"
    echo
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  build         Build the Docker image"
    echo "  dev           Start development environment"
    echo "  prod          Start production environment"
    echo "  stop          Stop all containers"
    echo "  clean         Clean up Docker resources"
    echo "  logs          Show container logs"
    echo "  help          Show this help message"
    echo
    echo "Examples:"
    echo "  $0 build                 # Build the image"
    echo "  $0 dev                   # Start development environment"
    echo "  $0 prod                  # Start production environment"
    echo "  $0 stop                  # Stop containers"
    echo "  $0 clean                 # Clean up everything"
}

# Show logs
show_logs() {
    log_info "Showing container logs..."
    
    if docker-compose -f "${COMPOSE_FILE}" ps -q > /dev/null 2>&1; then
        docker-compose -f "${COMPOSE_FILE}" logs -f
    elif docker-compose -f "${PROD_COMPOSE_FILE}" ps -q > /dev/null 2>&1; then
        docker-compose -f "${PROD_COMPOSE_FILE}" logs -f
    else
        log_error "No running containers found"
        exit 1
    fi
}

# Main script
main() {
    check_docker
    
    case "${1:-help}" in
        build)
            build_image
            ;;
        dev)
            build_image
            run_dev
            ;;
        prod)
            build_image
            run_prod
            ;;
        stop)
            stop
            ;;
        clean)
            clean
            ;;
        logs)
            show_logs
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@" 