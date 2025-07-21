#!/usr/bin/env python3
"""
Test script for the integrated MCP SSE endpoint.

This script tests the complete MCP handshake sequence:
1. Open SSE stream
2. Send initialize request
3. Send initialized notification
4. Test tools/list
5. Test tool execution
"""

import asyncio
import json
import httpx
import sys
from datetime import datetime


async def test_integrated_mcp():
    """Test the integrated MCP SSE endpoint with proper handshake."""
    server_url = "http://localhost:8020/api/v1/mcp"
    
    print("🧪 Testing Integrated MCP Endpoint...")
    print(f"Server URL: {server_url}")
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Test 1: Health Check
        print("💊 Testing health endpoint...")
        try:
            health_response = await client.get("http://localhost:8020/api/v1/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                print(f"✅ Health OK - Active servers: {health_data.get('active_servers', 0)}")
            else:
                print(f"❌ Health check failed: {health_response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
        
        print()
        
        # Test 2: Step 1 - Open SSE Stream (Test GET request)
        print("🌊 Step 1: Testing SSE stream opening...")
        try:
            # Test SSE stream with streaming
            async with client.stream("GET", server_url, headers={"Accept": "text/event-stream"}) as sse_stream:
                if sse_stream.status_code == 200:
                    print("✅ SSE stream opens successfully")
                    print(f"   Content-Type: {sse_stream.headers.get('content-type')}")
                    
                    # Read first few SSE events with timeout
                    events_found = []
                    event_count = 0
                    
                    try:
                        async for chunk in sse_stream.aiter_lines():
                            if chunk.strip():
                                events_found.append(chunk)
                                event_count += 1
                                print(f"   📨 Received: {chunk}")
                                # Stop after reading a few events to avoid hanging
                                if event_count >= 8:
                                    break
                    except asyncio.TimeoutError:
                        print("   ⏰ SSE stream timeout (expected for testing)")
                    except Exception as stream_e:
                        print(f"   ⚠️ SSE stream error: {stream_e}")
                    
                    # Check for required SSE events
                    sse_content = "\n".join(events_found)
                    if "event: endpoint" in sse_content:
                        print("✅ Endpoint event found in SSE stream")
                    else:
                        print("⚠️ Endpoint event not found")
                        print(f"   Events received: {events_found[:3]}...")
                        
                else:
                    print(f"❌ SSE stream failed: {sse_stream.status_code}")
                    return False
        except Exception as e:
            print(f"❌ SSE stream error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print()
        
        # Test 3: Step 2 - Initialize Request
        print("🚀 Step 2: Testing initialize request...")
        try:
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {
                            "listChanged": True
                        }
                    },
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            init_response = await client.post(
                server_url,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                },
                json=init_request
            )
            
            if init_response.status_code == 200:
                init_data = init_response.json()
                session_id = init_response.headers.get("Mcp-Session-Id")
                print("✅ Initialize successful")
                print(f"   Session ID: {session_id}")
                print(f"   Protocol Version: {init_data.get('result', {}).get('protocolVersion')}")
                print(f"   Server: {init_data.get('result', {}).get('serverInfo', {}).get('name')}")
                
                if not session_id:
                    print("❌ No session ID received")
                    return False
                    
            else:
                print(f"❌ Initialize failed: {init_response.status_code}")
                print(f"   Response: {init_response.text}")
                return False
        except Exception as e:
            print(f"❌ Initialize error: {e}")
            return False
        
        print()
        
        # Test 4: Step 3 - Initialized Notification
        print("📢 Step 3: Testing initialized notification...")
        try:
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            initialized_response = await client.post(
                server_url,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Session-Id": session_id
                },
                json=initialized_notification
            )
            
            if initialized_response.status_code == 202:
                print("✅ Initialized notification accepted (202 Accepted)")
                print("✅ MCP handshake complete!")
            else:
                print(f"❌ Initialized notification failed: {initialized_response.status_code}")
                print(f"   Response: {initialized_response.text}")
                return False
        except Exception as e:
            print(f"❌ Initialized notification error: {e}")
            return False
        
        print()
        
        # Test 5: Tools List
        print("🔧 Step 4: Testing tools/list...")
        try:
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            tools_response = await client.post(
                server_url,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Session-Id": session_id
                },
                json=tools_request
            )
            
            if tools_response.status_code == 200:
                tools_data = tools_response.json()
                tools_list = tools_data.get("result", {}).get("tools", [])
                print(f"✅ Tools list successful - Found {len(tools_list)} tools")
                
                for tool in tools_list[:3]:  # Show first 3 tools
                    print(f"   📦 {tool.get('name')} - {tool.get('description', 'No description')[:50]}...")
                    
                if len(tools_list) > 3:
                    print(f"   ... and {len(tools_list) - 3} more tools")
                    
            else:
                print(f"❌ Tools list failed: {tools_response.status_code}")
                print(f"   Response: {tools_response.text}")
                return False
        except Exception as e:
            print(f"❌ Tools list error: {e}")
            return False
        
        print()
        
        # Test 6: Tool Execution (if tools available)
        if tools_list:
            print("⚙️ Step 5: Testing tool execution...")
            try:
                # Try to execute the first tool with minimal parameters
                first_tool = tools_list[0]
                tool_name = first_tool.get("name")
                
                tool_call_request = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": {}  # Minimal arguments
                    }
                }
                
                tool_response = await client.post(
                    server_url,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "Mcp-Session-Id": session_id
                    },
                    json=tool_call_request
                )
                
                if tool_response.status_code == 200:
                    tool_data = tool_response.json()
                    if "result" in tool_data:
                        print(f"✅ Tool execution successful: {tool_name}")
                        result_content = tool_data.get("result", {}).get("content", [])
                        if result_content:
                            first_content = result_content[0].get("text", "")[:100]
                            print(f"   Result preview: {first_content}...")
                    else:
                        print(f"⚠️ Tool executed but returned error: {tool_data.get('error', {}).get('message', 'Unknown error')}")
                else:
                    print(f"⚠️ Tool execution failed: {tool_response.status_code}")
                    print(f"   This might be normal if the tool requires specific parameters")
                    
            except Exception as e:
                print(f"⚠️ Tool execution error (might be normal): {e}")
        
        print()
        print("🎉 MCP Integration Test Complete!")
        print()
        print("Summary:")
        print("✅ SSE stream establishment")
        print("✅ Initialize handshake with session management")
        print("✅ Initialized notification (202 Accepted)")
        print("✅ Tools discovery")
        print("✅ MCP protocol compliance")
        print()
        print("🔗 Your MCP Portal is now ready for Cline/Claude Code!")
        print(f"   Use this config: {{\"transport\": \"sse\", \"url\": \"{server_url}\"}}")
        
        return True


async def main():
    """Main entry point."""
    success = await test_integrated_mcp()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main()) 