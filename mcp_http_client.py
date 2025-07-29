"""
HTTP MCP Client for Remote Stardog MCP Server

This module provides an HTTP-based MCP client that can connect to a remote
Stardog MCP server running in a different container/service.
"""

import asyncio
import json
import logging
import httpx
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from urllib.parse import urljoin
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class MCPTool:
    """Represents an MCP tool with its metadata."""
    name: str
    description: str
    input_schema: Dict[str, Any]

@dataclass
class MCPToolResult:
    """Represents the result of an MCP tool execution."""
    content: List[Dict[str, Any]]
    is_error: bool = False

class HTTPMCPClient:
    """
    HTTP-based MCP client for connecting to remote MCP servers.
    
    This client communicates with an MCP server that has been enhanced
    with HTTP endpoints (typically using FastAPI).
    """
    
    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize the HTTP MCP client.
        
        Args:
            base_url: Base URL of the MCP server (e.g., "http://stardog-mcp:8000")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session: Optional[httpx.AsyncClient] = None
        self._tools: Dict[str, MCPTool] = {}
        self._initialized = False
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        
    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )
            
        try:
            # Test connection
            response = await self.session.get(f"{self.base_url}/health")
            response.raise_for_status()
            
            # Initialize and get available tools
            await self._initialize()
            
            logger.info("Connected to MCP server", base_url=self.base_url)
            
        except Exception as e:
            logger.error("Failed to connect to MCP server", error=str(e), base_url=self.base_url)
            if self.session:
                await self.session.aclose()
                self.session = None
            raise
            
    async def disconnect(self) -> None:
        """Close the connection to the MCP server."""
        if self.session:
            await self.session.aclose()
            self.session = None
            self._initialized = False
            logger.info("Disconnected from MCP server")
            
    async def _initialize(self) -> None:
        """Initialize the MCP session and get available tools."""
        if self._initialized:
            return
            
        try:
            # Send initialize request
            init_response = await self.session.post(
                f"{self.base_url}/initialize",
                json={"protocol_version": "1.0", "client_info": {"name": "stardog-strands-demo", "version": "1.0"}}
            )
            init_response.raise_for_status()
            
            # Get available tools
            await self._load_tools()
            
            self._initialized = True
            logger.info("MCP client initialized", tools_count=len(self._tools))
            
        except Exception as e:
            logger.error("Failed to initialize MCP client", error=str(e))
            raise
            
    async def _load_tools(self) -> None:
        """Load available tools from the MCP server."""
        try:
            response = await self.session.get(f"{self.base_url}/tools")
            response.raise_for_status()
            
            tools_data = response.json()
            self._tools = {}
            
            for tool_data in tools_data.get("tools", []):
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {})
                )
                self._tools[tool.name] = tool
                
            logger.info("Loaded MCP tools", tools=list(self._tools.keys()))
            
        except Exception as e:
            logger.error("Failed to load tools", error=str(e))
            raise
            
    async def list_tools(self) -> List[MCPTool]:
        """
        Get list of available tools.
        
        Returns:
            List of available MCP tools
        """
        if not self._initialized:
            await self._initialize()
            
        return list(self._tools.values())
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """
        Call an MCP tool with the given arguments.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Result of the tool execution
        """
        # Ensure we have a valid session and are initialized
        if not self.session or self.session.is_closed:
            await self.connect()
            
        if not self._initialized:
            await self._initialize()
            
        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {list(self._tools.keys())}")
            
        try:
            logger.info("Calling MCP tool", tool=tool_name, args=arguments)
            
            # Ensure session is still valid
            if self.session.is_closed:
                await self.connect()
            
            response = await self.session.post(
                f"{self.base_url}/tools/{tool_name}",
                json={"arguments": arguments}
            )
            response.raise_for_status()
            
            result_data = response.json()
            
            # Parse the result
            content = result_data.get("content", [])
            is_error = result_data.get("isError", False)
            
            logger.info("MCP tool completed", tool=tool_name, is_error=is_error)
            
            return MCPToolResult(content=content, is_error=is_error)
            
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling tool", tool=tool_name, status=e.response.status_code, error=str(e))
            return MCPToolResult(
                content=[{"type": "text", "text": f"HTTP error: {e.response.status_code} - {str(e)}"}],
                is_error=True
            )
        except Exception as e:
            logger.error("Error calling tool", tool=tool_name, error=str(e))
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                is_error=True
            )
            
    async def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the input schema for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool input schema or None if not found
        """
        if not self._initialized:
            await self._initialize()
            
        tool = self._tools.get(tool_name)
        return tool.input_schema if tool else None
        
    async def health_check(self) -> bool:
        """
        Check if the MCP server is healthy.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            if not self.session:
                return False
                
            response = await self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
            
        except Exception:
            return False
            
    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())


class StardogMCPClient(HTTPMCPClient):
    """
    Specialized MCP client for Stardog operations.
    
    Provides convenience methods for common Stardog operations.
    """
    
    async def execute_sparql(self, query: str, database: str = "stardog") -> MCPToolResult:
        """
        Execute a SPARQL query against Stardog.
        
        Args:
            query: SPARQL query to execute
            database: Stardog database name
            
        Returns:
            Query results
        """
        return await self.call_tool("execute_sparql", {
            "query": query,
            "database": database
        })
        
    async def text_to_sparql(self, text: str, database: str = "stardog") -> MCPToolResult:
        """
        Convert natural language text to SPARQL query.
        
        Args:
            text: Natural language query
            database: Stardog database name
            
        Returns:
            Generated SPARQL query
        """
        return await self.call_tool("text_to_sparql", {
            "text": text,
            "database": database
        })
        
    async def get_schema(self, database: str = "stardog") -> MCPToolResult:
        """
        Get the schema/ontology of a Stardog database.
        
        Args:
            database: Stardog database name
            
        Returns:
            Database schema information
        """
        return await self.call_tool("get_schema", {
            "database": database
        })
        
    async def list_databases(self) -> MCPToolResult:
        """
        List all available Stardog databases.
        
        Returns:
            List of databases
        """
        return await self.call_tool("list_databases", {})
        
    async def execute_graphql(self, query: str, database: str = "stardog") -> MCPToolResult:
        """
        Execute a GraphQL query against Stardog.
        
        Args:
            query: GraphQL query to execute
            database: Stardog database name
            
        Returns:
            Query results
        """
        return await self.call_tool("execute_graphql", {
            "query": query,
            "database": database
        })


# Utility function for creating client instances
async def create_stardog_client(base_url: str) -> StardogMCPClient:
    """
    Create and connect a Stardog MCP client.
    
    Args:
        base_url: Base URL of the Stardog MCP server
        
    Returns:
        Connected Stardog MCP client
    """
    client = StardogMCPClient(base_url)
    await client.connect()
    return client
