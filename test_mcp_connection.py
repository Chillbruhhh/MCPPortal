#!/usr/bin/env python3
"""
Test MCP Portal Connection

Simple test script to verify that Claude Code can connect to the MCP Portal.
"""

import asyncio
import sys
from claude_code_connector import get_mcp_client


async def test_connection():
    """Test connection to MCP Portal."""
    print("🔍 Testing MCP Portal connection...")
    
    # Check if MCP Portal is running
    client = get_mcp_client()
    
    try:
        # Test connection
        connected = await client.connect()
        
        if not connected:
            print("❌ Failed to connect to MCP Portal")
            print("💡 Make sure MCP Portal is running on http://localhost:8020")
            print("   You can start it with: python -m mcp_gateway.main")
            return False
        
        print("✅ Successfully connected to MCP Portal")
        
        # Test tool discovery
        tools = await client.list_tools()
        print(f"📋 Found {len(tools)} available tools:")
        
        for tool in tools:
            print(f"  🔧 {tool['name']}")
            print(f"     📝 {tool['description']}")
            if tool.get('inputSchema', {}).get('properties'):
                props = list(tool['inputSchema']['properties'].keys())
                print(f"     📥 Parameters: {', '.join(props)}")
            print()
        
        # Test simple tool execution if available
        if tools:
            print("🧪 Testing tool execution...")
            # Look for a simple tool to test
            test_tool = None
            for tool in tools:
                # Look for tools that might not require parameters
                if not tool.get('inputSchema', {}).get('required', []):
                    test_tool = tool
                    break
            
            if test_tool:
                print(f"   Testing: {test_tool['name']}")
                try:
                    result = await client.call_tool(test_tool['name'], {})
                    print(f"   ✅ Success: {str(result)[:100]}...")
                except Exception as e:
                    print(f"   ⚠️  Tool execution failed: {e}")
            else:
                print("   ℹ️  No parameter-free tools found for testing")
        
        await client.disconnect()
        print("👋 Connection test completed")
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)