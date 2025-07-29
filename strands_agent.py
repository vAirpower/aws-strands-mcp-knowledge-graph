"""
AWS Strands Agents Integration

This module provides integration with AWS Strands Agents for autonomous reasoning
and tool orchestration with the Stardog MCP server.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
import structlog

from mcp_http_client import StardogMCPClient, MCPToolResult

logger = structlog.get_logger(__name__)

@dataclass
class AgentMessage:
    """Represents a message in the agent conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class AgentContext:
    """Context information for the agent."""
    conversation_id: str
    user_id: Optional[str] = None
    session_data: Optional[Dict[str, Any]] = None
    memory: Optional[Dict[str, Any]] = None

@dataclass
class ToolCall:
    """Represents a tool call made by the agent."""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str
    timestamp: datetime

@dataclass
class ToolResult:
    """Represents the result of a tool call."""
    call_id: str
    content: str
    is_error: bool = False
    metadata: Optional[Dict[str, Any]] = None

class StrandsMCPTool:
    """
    Wrapper class for MCP tools to be used with Strands Agents.
    """
    
    def __init__(self, name: str, description: str, mcp_client: StardogMCPClient, tool_name: str):
        self.name = name
        self.description = description
        self.mcp_client = mcp_client
        self.tool_name = tool_name
        
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute the MCP tool with given arguments."""
        try:
            result = await self.mcp_client.call_tool(self.tool_name, arguments)
            
            # Convert MCP result to tool result
            content_text = ""
            for content_item in result.content:
                if content_item.get("type") == "text":
                    content_text += content_item.get("text", "")
                    
            return ToolResult(
                call_id=f"{self.tool_name}_{datetime.now().timestamp()}",
                content=content_text,
                is_error=result.is_error,
                metadata={"tool_name": self.tool_name, "arguments": arguments}
            )
            
        except Exception as e:
            logger.error("Error executing MCP tool", tool=self.tool_name, error=str(e))
            return ToolResult(
                call_id=f"{self.tool_name}_{datetime.now().timestamp()}",
                content=f"Error executing tool: {str(e)}",
                is_error=True,
                metadata={"tool_name": self.tool_name, "error": str(e)}
            )

class StrandsAgent:
    """
    AWS Strands Agent with MCP tool integration.
    
    This agent provides autonomous reasoning capabilities and can orchestrate
    MCP tools to answer user queries about knowledge graphs.
    """
    
    def __init__(
        self,
        agent_name: str,
        model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        mcp_client: Optional[StardogMCPClient] = None,
        region: str = "us-east-1"
    ):
        """
        Initialize the Strands Agent.
        
        Args:
            agent_name: Name of the agent
            model_id: Bedrock model ID to use
            mcp_client: Connected MCP client for tool access
            region: AWS region
        """
        self.agent_name = agent_name
        self.model_id = model_id
        self.mcp_client = mcp_client
        self.region = region
        
        # Initialize Bedrock client
        self.bedrock = boto3.client('bedrock-runtime', region_name=region)
        
        # Tool registry
        self.tools: Dict[str, StrandsMCPTool] = {}
        self.conversation_history: List[AgentMessage] = []
        
        # Agent configuration
        self.system_prompt = self._create_system_prompt()
        self.max_iterations = 5
        
    def _create_system_prompt(self) -> str:
        """Create the system prompt for the agent."""
        return """
You are an intelligent agent that can answer questions about knowledge graphs and geospatial intelligence data.

You have access to tools that can:
1. Convert natural language to SPARQL queries
2. Execute SPARQL queries against knowledge graphs
3. Explore database schemas and ontologies
4. Execute GraphQL queries

Your capabilities:
- Analyze user questions and determine the best approach
- Use available tools autonomously to gather information
- Synthesize results from multiple tool calls
- Provide clear, informative responses

When answering questions:
1. First understand what the user is asking
2. Determine which tools you need to use
3. Make tool calls to gather information
4. Analyze and synthesize the results
5. Provide a comprehensive answer

Be thorough in your analysis and always explain your reasoning process.
"""
        
    async def initialize_tools(self) -> None:
        """Initialize MCP tools for the agent."""
        if not self.mcp_client:
            logger.warning("No MCP client provided, tools will not be available")
            return
            
        try:
            # Get available tools from MCP server
            available_tools = await self.mcp_client.list_tools()
            
            # Register each tool
            for mcp_tool in available_tools:
                strands_tool = StrandsMCPTool(
                    name=mcp_tool.name,
                    description=mcp_tool.description,
                    mcp_client=self.mcp_client,
                    tool_name=mcp_tool.name
                )
                self.tools[mcp_tool.name] = strands_tool
                
            logger.info("Initialized agent tools", tool_count=len(self.tools), tools=list(self.tools.keys()))
            
        except Exception as e:
            logger.error("Failed to initialize tools", error=str(e))
            
    async def process_query(self, user_query: str, context: Optional[AgentContext] = None) -> str:
        """
        Process a user query using autonomous reasoning and tool orchestration.
        
        Args:
            user_query: The user's question or request
            context: Optional context information
            
        Returns:
            The agent's response
        """
        try:
            # Add user message to history
            user_message = AgentMessage(
                role="user",
                content=user_query,
                timestamp=datetime.now()
            )
            self.conversation_history.append(user_message)
            
            # Initialize reasoning loop
            response = await self._reasoning_loop(user_query, context)
            
            # Add assistant response to history
            assistant_message = AgentMessage(
                role="assistant",
                content=response,
                timestamp=datetime.now()
            )
            self.conversation_history.append(assistant_message)
            
            return response
            
        except Exception as e:
            logger.error("Error processing query", error=str(e))
            return f"I encountered an error while processing your query: {str(e)}"
            
    async def _reasoning_loop(self, user_query: str, context: Optional[AgentContext] = None) -> str:
        """
        Main reasoning loop that orchestrates tool calls and generates responses.
        """
        iteration = 0
        reasoning_context = {"user_query": user_query, "tool_results": []}
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Generate next action using Bedrock
            action = await self._generate_next_action(reasoning_context, iteration)
            
            if action["type"] == "tool_call":
                # Execute tool call
                tool_result = await self._execute_tool_call(action)
                reasoning_context["tool_results"].append(tool_result)
                
            elif action["type"] == "final_answer":
                # Generate final response
                return action["content"]
                
            elif action["type"] == "clarification":
                # Need more information from user
                return action["content"]
                
        # If we've reached max iterations, generate a response based on what we have
        return await self._generate_final_response(reasoning_context)
        
    async def _generate_next_action(self, context: Dict[str, Any], iteration: int) -> Dict[str, Any]:
        """
        Generate the next action for the agent using Bedrock.
        """
        # Build conversation history for Bedrock
        messages = []
        
        # Add conversation history (excluding system messages)
        for msg in self.conversation_history[-5:]:  # Last 5 messages for context
            if msg.role in ["user", "assistant"] and msg.content.strip():
                messages.append({
                    "role": msg.role,
                    "content": [{"text": msg.content}]
                })
        
        # Add current reasoning context
        reasoning_prompt = self._build_reasoning_prompt(context, iteration)
        if reasoning_prompt.strip():  # Only add if not empty
            messages.append({
                "role": "user",
                "content": [{"text": reasoning_prompt}]
            })
        
        # System prompts go in the system parameter, not as messages
        system_prompts = [{"text": self.system_prompt}]
        
        # Call Bedrock
        try:
            response = self.bedrock.converse(
                modelId=self.model_id,
                messages=messages,
                system=system_prompts,
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.3,
                    "topP": 0.9
                }
            )
            
            response_text = response['output']['message']['content'][0]['text']
            
            # Parse the response to determine action
            return self._parse_action_response(response_text)
            
        except Exception as e:
            logger.error("Error generating next action", error=str(e))
            return {"type": "final_answer", "content": f"I encountered an error: {str(e)}"}
            
    def _build_reasoning_prompt(self, context: Dict[str, Any], iteration: int) -> str:
        """Build the reasoning prompt for the current iteration."""
        prompt = f"""
Current iteration: {iteration}/{self.max_iterations}

User Query: {context['user_query']}

Available Tools:
{self._format_available_tools()}

Previous Tool Results:
{self._format_tool_results(context['tool_results'])}

Based on the user query and any previous tool results, what should I do next?

Respond with one of these actions:
1. TOOL_CALL: If you need to use a tool, respond with:
   ACTION: TOOL_CALL
   TOOL: <tool_name>
   ARGUMENTS: <json_arguments>
   REASONING: <why you're using this tool>

2. FINAL_ANSWER: If you have enough information to answer, respond with:
   ACTION: FINAL_ANSWER
   CONTENT: <your complete answer>

3. CLARIFICATION: If you need more information from the user, respond with:
   ACTION: CLARIFICATION
   CONTENT: <what you need to know>

Choose the most appropriate action:
"""
        return prompt
        
    def _format_available_tools(self) -> str:
        """Format available tools for the prompt."""
        if not self.tools:
            return "No tools available"
            
        tool_descriptions = []
        for tool_name, tool in self.tools.items():
            tool_descriptions.append(f"- {tool_name}: {tool.description}")
            
        return "\n".join(tool_descriptions)
        
    def _format_tool_results(self, tool_results: List[ToolResult]) -> str:
        """Format tool results for the prompt."""
        if not tool_results:
            return "No previous tool results"
            
        formatted_results = []
        for result in tool_results:
            status = "ERROR" if result.is_error else "SUCCESS"
            formatted_results.append(f"- {result.metadata.get('tool_name', 'Unknown')}: {status}\n  {result.content[:200]}...")
            
        return "\n".join(formatted_results)
        
    def _parse_action_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the action response from Bedrock."""
        lines = response_text.strip().split('\n')
        action_line = None
        
        for line in lines:
            if line.startswith('ACTION:'):
                action_line = line.split('ACTION:')[1].strip()
                break
                
        if not action_line:
            # If no action found, assume final answer
            return {"type": "final_answer", "content": response_text}
            
        if action_line == "TOOL_CALL":
            # Parse tool call
            tool_name = None
            arguments = {}
            reasoning = ""
            
            for line in lines:
                if line.startswith('TOOL:'):
                    tool_name = line.split('TOOL:')[1].strip()
                elif line.startswith('ARGUMENTS:'):
                    args_text = line.split('ARGUMENTS:')[1].strip()
                    
                    # More robust JSON parsing
                    if args_text:
                        try:
                            # Try direct JSON parsing first
                            arguments = json.loads(args_text)
                        except json.JSONDecodeError:
                            # If that fails, try to extract arguments manually
                            arguments = self._extract_arguments_fallback(args_text)
                    else:
                        arguments = {}
                        
                elif line.startswith('REASONING:'):
                    reasoning = line.split('REASONING:')[1].strip()
                    
            logger.info(f"Parsed tool call: {tool_name} with args: {arguments}")
                    
            return {
                "type": "tool_call",
                "tool_name": tool_name,
                "arguments": arguments,
                "reasoning": reasoning
            }
            
        elif action_line == "FINAL_ANSWER":
            content = ""
            content_started = False
            for line in lines:
                if line.startswith('CONTENT:'):
                    content = line.split('CONTENT:')[1].strip()
                    content_started = True
                elif content_started:
                    # Continue capturing content on subsequent lines
                    content += "\n" + line
            return {"type": "final_answer", "content": content}
            
        elif action_line == "CLARIFICATION":
            content = ""
            content_started = False
            for line in lines:
                if line.startswith('CONTENT:'):
                    content = line.split('CONTENT:')[1].strip()
                    content_started = True
                elif content_started:
                    # Continue capturing content on subsequent lines
                    content += "\n" + line
            return {"type": "clarification", "content": content}
            
        else:
            return {"type": "final_answer", "content": response_text}
            
    def _extract_arguments_fallback(self, args_text: str) -> Dict[str, Any]:
        """Extract arguments from text when JSON parsing fails."""
        arguments = {}
        
        # Common patterns to extract
        patterns = [
            (r'"location":\s*"([^"]+)"', 'location'),
            (r'"query":\s*"([^"]+)"', 'query'),
            (r'"facility_type":\s*"([^"]+)"', 'facility_type'),
            (r'"text":\s*"([^"]+)"', 'text'),
            (r'"limit":\s*(\d+)', 'limit'),
        ]
        
        import re
        for pattern, key in patterns:
            match = re.search(pattern, args_text)
            if match:
                value = match.group(1)
                # Convert to int if it's a number
                if key == 'limit' and value.isdigit():
                    arguments[key] = int(value)
                else:
                    arguments[key] = value
        
        # Simple keyword extraction as final fallback
        if not arguments:
            if 'virginia' in args_text.lower():
                arguments['location'] = 'Virginia'
            elif 'washington' in args_text.lower():
                arguments['location'] = 'Washington DC'
            elif 'military' in args_text.lower() or 'base' in args_text.lower():
                arguments['facility_type'] = 'Military Base'
                
        logger.info(f"Fallback argument extraction: {arguments} from: {args_text}")
        return arguments
            
    async def _execute_tool_call(self, action: Dict[str, Any]) -> ToolResult:
        """Execute a tool call."""
        tool_name = action.get("tool_name")
        arguments = action.get("arguments", {})
        
        if tool_name not in self.tools:
            return ToolResult(
                call_id=f"error_{datetime.now().timestamp()}",
                content=f"Tool '{tool_name}' not found. Available tools: {list(self.tools.keys())}",
                is_error=True
            )
            
        tool = self.tools[tool_name]
        return await tool.execute(arguments)
        
    async def _generate_final_response(self, context: Dict[str, Any]) -> str:
        """Generate a final response based on the accumulated context."""
        # Use Bedrock to synthesize the final answer
        synthesis_prompt = f"""
Based on the following information, provide a comprehensive answer to the user's query.

User Query: {context['user_query']}

Tool Results:
{self._format_tool_results(context['tool_results'])}

Please synthesize this information into a clear, helpful response:
"""
        
        try:
            if synthesis_prompt.strip():  # Only call if we have content
                response = self.bedrock.converse(
                    modelId=self.model_id,
                    messages=[{
                        "role": "user",
                        "content": [{"text": synthesis_prompt}]
                    }],
                    inferenceConfig={
                        "maxTokens": 2048,
                        "temperature": 0.3
                    }
                )
                
                return response['output']['message']['content'][0]['text']
            else:
                return "I was unable to generate a response due to empty content."
            
        except Exception as e:
            logger.error("Error generating final response", error=str(e))
            return f"I gathered some information but encountered an error generating the final response: {str(e)}"
            
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        return [asdict(msg) for msg in self.conversation_history]
        
    def clear_conversation_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_history = []


async def create_strands_agent(
    mcp_server_url: str,
    agent_name: str = "StarDog Knowledge Agent",
    model_id: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
) -> StrandsAgent:
    """
    Create and initialize a Strands Agent with MCP tools.
    
    Args:
        mcp_server_url: URL of the Stardog MCP server
        agent_name: Name for the agent
        model_id: Bedrock model ID to use
        
    Returns:
        Initialized Strands Agent
    """
    from mcp_http_client import create_stardog_client
    
    # Create MCP client
    mcp_client = await create_stardog_client(mcp_server_url)
    
    # Create agent
    agent = StrandsAgent(
        agent_name=agent_name,
        model_id=model_id,
        mcp_client=mcp_client
    )
    
    # Initialize tools
    await agent.initialize_tools()
    
    return agent
