#!/usr/bin/env python3
"""
Dynamic Docker runner for MCP Portal.

This script automatically detects the user's MCP configuration directories
and runs the Docker container with the correct volume mounts.
"""

import os
import subprocess
import sys
from pathlib import Path
import platform

def get_user_config_paths():
    """Get user-specific configuration paths based on the operating system."""
    home = Path.home()
    system = platform.system()
    
    paths = {}
    
    if system == "Windows":
        # Windows paths
        paths["cursor"] = home / ".cursor"
        paths["vscode"] = home / "AppData" / "Roaming" / "Code" / "User"
        paths["claude"] = home / "AppData" / "Roaming" / "Claude"
        paths["windsurf"] = home / ".windsurf"
        paths["codeium"] = home / "AppData" / "Roaming" / "Codeium"
        
    elif system == "Darwin":  # macOS
        paths["cursor"] = home / ".cursor"
        paths["vscode"] = home / "Library" / "Application Support" / "Code" / "User"
        paths["claude"] = home / "Library" / "Application Support" / "Claude"
        paths["windsurf"] = home / ".windsurf"
        paths["codeium"] = home / "Library" / "Application Support" / "Codeium"
        
    else:  # Linux
        paths["cursor"] = home / ".cursor"
        paths["vscode"] = home / ".config" / "Code" / "User"
        paths["claude"] = home / ".config" / "claude"
        paths["windsurf"] = home / ".windsurf"
        paths["codeium"] = home / ".config" / "Codeium"
    
    return paths

def create_docker_command():
    """Create the Docker command with dynamic volume mounts."""
    config_paths = get_user_config_paths()
    
    # Base Docker command
    cmd = [
        "docker", "run", "-d",
        "-p", "8020:8020",
        "--user", "root",
        "--name", "mcp-portal-container",
        "-v", "/var/run/docker.sock:/var/run/docker.sock"  # Docker-in-Docker
    ]
    
    # Add volume mounts for existing configuration directories
    for ide_name, local_path in config_paths.items():
        if local_path.exists():
            # Convert to Docker volume format
            host_path = str(local_path.absolute())
            container_path = f"/root/.{ide_name}"
            
            # For Windows, convert C:\Users\... to /c/Users/...
            if platform.system() == "Windows":
                host_path = host_path.replace("\\", "/")
                if host_path.startswith("C:/"):
                    host_path = "/c/" + host_path[3:]
                elif host_path.startswith("D:/"):
                    host_path = "/d/" + host_path[3:]
                # Add more drive letters as needed
            
            cmd.extend(["-v", f"{host_path}:{container_path}"])
            print(f"✓ Found {ide_name} config at: {local_path}")
        else:
            print(f"✗ No {ide_name} config found at: {local_path}")
    
    # Add the image name
    cmd.append("mcp-gateway")
    
    return cmd

def main():
    """Main function to run the Docker container."""
    print("🔍 Detecting MCP configuration directories...")
    print(f"Operating System: {platform.system()}")
    print(f"User Home: {Path.home()}")
    print()
    
    # Stop and remove existing container if it exists
    try:
        subprocess.run(["docker", "stop", "mcp-portal-container"], 
                      capture_output=True, check=False)
        subprocess.run(["docker", "rm", "mcp-portal-container"], 
                      capture_output=True, check=False)
    except:
        pass
    
    # Create and run the Docker command
    cmd = create_docker_command()
    
    print("\n🚀 Starting MCP Portal container...")
    print("Command:", " ".join(cmd))
    print()
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Container started successfully!")
        print(f"Container ID: {result.stdout.strip()}")
        print("\n🌐 MCP Portal is running at: http://localhost:8020")
        print("\n📊 To view logs: docker logs mcp-portal-container")
        print("🛑 To stop: docker stop mcp-portal-container")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start container: {e}")
        print(f"Error output: {e.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Docker not found. Please install Docker first.")
        sys.exit(1)

if __name__ == "__main__":
    main() 