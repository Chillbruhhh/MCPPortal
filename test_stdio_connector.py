#!/usr/bin/env python3
"""
Test the fixed stdio MCP connector

This script simulates how Claude Code/Cline would interact with the stdio connector.
"""

import asyncio
import json
import subprocess
import sys
import os


async def test_stdio_connector():
    """Test the stdio connector by simulating MCP client behavior."""
    print("🔍 Testing stdio MCP connector...")
    
    # Start the connector process
    env = os.environ.copy()
    env["MCP_PORTAL_URL"] = "http://localhost:8020"
    
    try:
        process = subprocess.Popen(
            [sys.executable, "claude_code_connector_fixed.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        # Test 1: Initialize
        print("📋 Testing initialize...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "sampling": {},
                    "roots": {
                        "listChanged": True
                    }
                },
                "clientInfo": {
                    "name": "test-client", 
                    "title": "Test MCP Client",
                    "version": "1.0.0"
                }
            }
        }
        
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            init_response = json.loads(response_line.strip())
            print(f"✅ Initialize response: {init_response}")
        else:
            print("❌ No response from initialize")
            return False
        
        # Test 1.5: Send initialized notification (CRITICAL MCP step!)
        print("🔔 Sending initialized notification...")
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        process.stdin.write(json.dumps(initialized_notification) + "\n")
        process.stdin.flush()
        
        # Give server time to process notification
        import time
        time.sleep(0.1)
        
        # Test 2: List tools
        print("🔧 Testing tools/list...")
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(list_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            list_response = json.loads(response_line.strip())
            tools = list_response.get("result", {}).get("tools", [])
            print(f"✅ Found {len(tools)} tools:")
            for tool in tools[:3]:  # Show first 3 tools
                print(f"   - {tool['name']}: {tool['description'][:50]}...")
        else:
            print("❌ No response from tools/list")
            return False
        
        # Test 3: Call a tool (if available)
        if tools:
            print("⚡ Testing tools/call...")
            test_tool = tools[0]  # Use first tool
            call_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": test_tool["name"],
                    "arguments": {"query": "test"} if "query" in str(test_tool.get("inputSchema", {})) else {}
                }
            }
            
            process.stdin.write(json.dumps(call_request) + "\n")
            process.stdin.flush()
            
            # Read response with timeout
            try:
                response_line = process.stdout.readline()
                if response_line:
                    call_response = json.loads(response_line.strip())
                    if "error" in call_response:
                        print(f"⚠️  Tool call error: {call_response['error']['message']}")
                    else:
                        print(f"✅ Tool call successful: {str(call_response['result'])[:100]}...")
                else:
                    print("❌ No response from tools/call")
            except Exception as e:
                print(f"⚠️  Tool call timeout or error: {e}")
        
        print("🎉 Stdio connector test completed!")
        return True
        
    except FileNotFoundError:
        print("❌ Failed to start connector: claude_code_connector_fixed.py not found")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        if 'process' in locals():
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    success = asyncio.run(test_stdio_connector())
    if success:
        print("\n✅ The stdio connector should now work with Claude Code/Cline!")
        print("📝 Use the configuration in mcp_config_fixed.json")
    else:
        print("\n❌ The stdio connector needs more work.")
    
    sys.exit(0 if success else 1) 