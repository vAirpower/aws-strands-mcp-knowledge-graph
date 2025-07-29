"""
Stardog Strands Demo - Streamlit Chatbot

A simple chatbot that demonstrates integration of:
- AWS Bedrock Converse API with Claude 3.7 Sonnet
- AWS Strands Agents for autonomous reasoning
- Remote HTTP MCP client connecting to Stardog MCP Server
- Knowledge graph querying capabilities
"""

import streamlit as st
import asyncio
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog
from dotenv import load_dotenv

# Import our custom modules
from strands_agent import StrandsAgent, create_strands_agent, AgentContext
from mcp_http_client import StardogMCPClient, create_stardog_client
from graph_visualizer import (
    create_knowledge_graph_from_mcp_results,
    extract_graph_context_from_interaction,
    render_knowledge_graph
)

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="Stardog Strands Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
FUSEKI_MCP_SERVER_URL = os.getenv("FUSEKI_MCP_SERVER_URL", "http://localhost:8000")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    if "agent" not in st.session_state:
        st.session_state.agent = None
        
    if "agent_initialized" not in st.session_state:
        st.session_state.agent_initialized = False
        
    if "mcp_client" not in st.session_state:
        st.session_state.mcp_client = None
        
    if "connection_status" not in st.session_state:
        st.session_state.connection_status = {"status": "disconnected", "message": "Not connected"}
        
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    # Graph visualization session state
    if "show_graph" not in st.session_state:
        st.session_state.show_graph = False
        
    if "last_graph_data" not in st.session_state:
        st.session_state.last_graph_data = None
        
    if "last_tool_results" not in st.session_state:
        st.session_state.last_tool_results = []
        
    if "last_user_query" not in st.session_state:
        st.session_state.last_user_query = ""
        
    if "last_agent_response" not in st.session_state:
        st.session_state.last_agent_response = ""

async def connect_to_mcp_server(server_url: str) -> bool:
    """Connect to the MCP server and test the connection."""
    try:
        st.session_state.mcp_client = await create_stardog_client(server_url)
        
        # Test connection by listing tools
        tools = await st.session_state.mcp_client.list_tools()
        
        st.session_state.connection_status = {
            "status": "connected",
            "message": f"Connected to MCP server. {len(tools)} tools available.",
            "tools": [tool.name for tool in tools]
        }
        
        logger.info("MCP server connection successful", server_url=server_url, tools_count=len(tools))
        return True
        
    except Exception as e:
        st.session_state.connection_status = {
            "status": "error",
            "message": f"Failed to connect to MCP server: {str(e)}",
            "tools": []
        }
        logger.error("MCP server connection failed", error=str(e), server_url=server_url)
        return False

async def initialize_agent(server_url: str, model_id: str) -> bool:
    """Initialize the Strands Agent with MCP tools."""
    try:
        # First ensure MCP connection
        if not st.session_state.mcp_client:
            success = await connect_to_mcp_server(server_url)
            if not success:
                return False
        
        # Create the Strands agent
        st.session_state.agent = StrandsAgent(
            agent_name="Stardog Knowledge Agent",
            model_id=model_id,
            mcp_client=st.session_state.mcp_client,
            region=AWS_REGION
        )
        
        # Initialize tools
        await st.session_state.agent.initialize_tools()
        
        st.session_state.agent_initialized = True
        logger.info("Strands agent initialized successfully")
        return True
        
    except Exception as e:
        st.error(f"Failed to initialize agent: {str(e)}")
        logger.error("Agent initialization failed", error=str(e))
        return False

async def process_user_message(user_input: str) -> str:
    """Process user message through the Strands Agent."""
    try:
        if not st.session_state.agent or not st.session_state.agent_initialized:
            return "Agent not initialized. Please check your configuration and try again."
        
        # Store the user query for graph context
        st.session_state.last_user_query = user_input
        
        # Create agent context
        context = AgentContext(
            conversation_id=st.session_state.conversation_id,
            user_id="demo_user",
            session_data={"timestamp": datetime.now().isoformat()}
        )
        
        # Process the query through the agent
        response = await st.session_state.agent.process_query(user_input, context)
        
        # Store the agent response for graph context
        st.session_state.last_agent_response = response
        
        # Extract tool results for graph visualization
        await extract_tool_results_for_graph(user_input, response)
        
        logger.info("User query processed", query=user_input[:100], response_length=len(response))
        return response
        
    except Exception as e:
        error_msg = f"Error processing query: {str(e)}"
        logger.error("Query processing failed", error=str(e), query=user_input[:100])
        return error_msg

async def extract_tool_results_for_graph(user_query: str, agent_response: str):
    """Extract tool results from the recent agent interaction for graph visualization."""
    try:
        # First, try to parse the agent response directly since it contains structured data
        tool_results = []
        
        # Create a mock tool result from the agent response for graph parsing
        if agent_response and len(agent_response.strip()) > 0:
            # The agent response often contains structured data that can be parsed
            mock_result = {
                "content": [
                    {
                        "type": "text",
                        "text": agent_response
                    }
                ]
            }
            tool_results.append(mock_result)
            logger.info(f"Created mock tool result from agent response: {len(agent_response)} characters")
        
        # Also try to get additional data from MCP tools if available
        if st.session_state.mcp_client:
            
            # For location-based queries, try get_facilities_near
            if any(location in user_query.lower() for location in ['washington', 'virginia', 'maryland', 'dc']):
                for location in ['Washington DC', 'Virginia', 'Maryland']:
                    if location.lower() in user_query.lower():
                        try:
                            result = await st.session_state.mcp_client.call_tool(
                                "get_facilities_near", 
                                {"location": location, "limit": 20}
                            )
                            tool_results.append(result)
                            logger.info(f"Added MCP tool result for location: {location}")
                            break
                        except Exception as e:
                            logger.warning(f"Failed to call get_facilities_near for {location}: {str(e)}")
            
            # For facility type queries, try facility searches
            elif any(facility_type in user_query.lower() for facility_type in ['military', 'base', 'airport', 'government']):
                try:
                    result = await st.session_state.mcp_client.call_tool(
                        "get_sample_data", 
                        {"limit": 50}
                    )
                    tool_results.append(result)
                    logger.info("Added MCP sample data result for facility type query")
                except Exception as e:
                    logger.warning(f"Failed to call get_sample_data: {str(e)}")
            
            # For general queries, get sample data
            else:
                try:
                    result = await st.session_state.mcp_client.call_tool(
                        "get_sample_data", 
                        {"limit": 30}
                    )
                    tool_results.append(result)
                    logger.info("Added MCP sample data result for general query")
                except Exception as e:
                    logger.warning(f"Failed to call get_sample_data: {str(e)}")
        
        # Store results for graph generation
        if tool_results:
            st.session_state.last_tool_results = tool_results
            logger.info(f"Stored {len(tool_results)} tool results for graph generation")
            
            # Auto-generate graph if visualization is enabled
            if st.session_state.show_graph:
                try:
                    graph = create_knowledge_graph_from_mcp_results(tool_results)
                    nodes_count = len(graph.nodes())
                    edges_count = len(graph.edges())
                    
                    if nodes_count > 0:
                        st.session_state.last_graph_data = {
                            'graph': graph,
                            'physics': True,
                            'height': 500
                        }
                        logger.info(f"Successfully created graph with {nodes_count} nodes and {edges_count} edges")
                    else:
                        logger.warning("Graph creation resulted in empty graph")
                        
                except Exception as e:
                    logger.error("Failed to create knowledge graph", error=str(e))
        else:
            logger.warning("No tool results available for graph generation")
        
    except Exception as e:
        logger.error("Failed to extract tool results for graph", error=str(e))

def render_knowledge_graph_section():
    """Render the knowledge graph visualization section."""
    if not st.session_state.show_graph:
        return
        
    st.header("🕸️ Knowledge Graph Visualization")
    
    if st.session_state.last_graph_data:
        try:
            graph_data = st.session_state.last_graph_data
            graph = graph_data['graph']
            
            if len(graph.nodes()) > 0:
                st.info(f"Displaying knowledge graph with {len(graph.nodes())} nodes and {len(graph.edges())} relationships")
                
                # Render the interactive graph
                result = render_knowledge_graph(
                    graph,
                    height=graph_data.get('height', 500),
                    physics_enabled=graph_data.get('physics', True)
                )
                
                # Show graph statistics
                with st.expander("📊 Graph Statistics"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Nodes", len(graph.nodes()))
                    with col2:
                        st.metric("Edges", len(graph.edges()))
                        
                    # Node type breakdown
                    node_types = {}
                    for node_id in graph.nodes():
                        node_data = graph.nodes[node_id]
                        node_type = node_data.get('type', 'Unknown')
                        node_types[node_type] = node_types.get(node_type, 0) + 1
                    
                    st.write("**Node Types:**")
                    for node_type, count in node_types.items():
                        st.write(f"• {node_type}: {count}")
                        
            else:
                st.warning("Knowledge graph is empty. Try asking a question about facilities or locations.")
                
        except Exception as e:
            st.error(f"Error rendering knowledge graph: {str(e)}")
            logger.error("Knowledge graph rendering failed", error=str(e))
    else:
        st.info("💡 Ask a question about facilities, locations, or the knowledge graph to see visualization here.")
        
        # Show some sample queries specific to graph visualization
        with st.expander("🎯 Queries that work well with graph visualization"):
            st.markdown("""
            **Location-based queries:**
            - "What facilities are near Washington DC?"
            - "Show me military bases in Virginia"
            - "Find airports in the region"
            
            **Entity exploration:**
            - "Tell me about the Pentagon"
            - "What's near the White House?"
            - "Show me government buildings"
            
            **Relationship queries:**
            - "What facilities are connected to each other?"
            - "Find entities in the same location"
            - "Show me the knowledge graph structure"
            """)

def render_sidebar():
    """Render the sidebar with configuration and status."""
    with st.sidebar:
        st.header("🔧 Configuration")
        
        # MCP Server Configuration
        st.subheader("MCP Server")
        server_url = st.text_input(
            "Server URL",
            value=FUSEKI_MCP_SERVER_URL,
            help="URL of the Fuseki MCP server"
        )
        
        # Model Configuration
        st.subheader("AI Model")
        model_id = st.selectbox(
            "Bedrock Model",
            [
                "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "us.anthropic.claude-3-haiku-20240307-v1:0"
            ],
            index=0,
            help="Choose the Bedrock model to use"
        )
        
        # Connection Controls
        st.subheader("Connection")
        
        if st.button("🔌 Connect to MCP Server", type="primary"):
            with st.spinner("Connecting to MCP server..."):
                success = asyncio.run(connect_to_mcp_server(server_url))
                if success:
                    st.success("Connected successfully!")
                    st.rerun()
                else:
                    st.error("Connection failed!")
        
        if st.button("🤖 Initialize Agent"):
            if st.session_state.connection_status["status"] != "connected":
                st.error("Please connect to MCP server first!")
            else:
                with st.spinner("Initializing Strands Agent..."):
                    success = asyncio.run(initialize_agent(server_url, model_id))
                    if success:
                        st.success("Agent initialized!")
                        st.rerun()
                    else:
                        st.error("Agent initialization failed!")
        
        # Status Display
        st.subheader("📊 Status")
        
        # Connection Status
        status = st.session_state.connection_status["status"]
        if status == "connected":
            st.success(f"✅ {st.session_state.connection_status['message']}")
            
            # Show available tools
            if "tools" in st.session_state.connection_status:
                with st.expander("Available MCP Tools"):
                    for tool in st.session_state.connection_status["tools"]:
                        st.write(f"• {tool}")
        elif status == "error":
            st.error(f"❌ {st.session_state.connection_status['message']}")
        else:
            st.warning("🔌 Not connected to MCP server")
        
        # Agent Status
        if st.session_state.agent_initialized:
            st.success("✅ Strands Agent Ready")
            
            # Show agent tools
            if st.session_state.agent:
                tool_count = len(st.session_state.agent.tools)
                st.info(f"🔧 {tool_count} tools loaded")
        else:
            st.warning("🤖 Agent not initialized")
        
        # Graph Visualization Controls
        st.subheader("📊 Graph Visualization")
        st.session_state.show_graph = st.checkbox(
            "Show Knowledge Graph",
            value=st.session_state.show_graph,
            help="Display interactive knowledge graph based on query results"
        )
        
        if st.session_state.show_graph:
            # Graph visualization options
            with st.expander("Graph Settings"):
                physics_enabled = st.checkbox("Enable Physics", value=True, help="Enable graph physics simulation")
                graph_height = st.slider("Graph Height", min_value=300, max_value=800, value=500, help="Height of graph display")
                
                if st.button("🔄 Refresh Graph"):
                    if st.session_state.last_tool_results:
                        try:
                            graph = create_knowledge_graph_from_mcp_results(st.session_state.last_tool_results)
                            st.session_state.last_graph_data = {
                                'graph': graph,
                                'physics': physics_enabled,
                                'height': graph_height
                            }
                            st.success("Graph refreshed!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error refreshing graph: {str(e)}")
                    else:
                        st.warning("No tool results available. Please ask a question first.")
        
        # Clear conversation
        st.subheader("🗑️ Actions")
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            st.session_state.last_graph_data = None
            st.session_state.last_tool_results = []
            st.session_state.last_user_query = ""
            st.session_state.last_agent_response = ""
            if st.session_state.agent:
                st.session_state.agent.clear_conversation_history()
            st.rerun()

def render_chat_interface():
    """Render the main chat interface."""
    st.header("🤖 Stardog Knowledge Assistant")
    st.caption("Ask questions about knowledge graphs and geospatial intelligence data")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show timestamp
            if "timestamp" in message:
                st.caption(f"*{message['timestamp']}*")
    
    # Chat input
    if prompt := st.chat_input("Ask me about knowledge graphs, locations, or facilities..."):
        # Check if agent is ready
        if not st.session_state.agent_initialized:
            st.error("Please initialize the agent first using the sidebar controls!")
            return
        
        # Add user message to chat
        timestamp = datetime.now().strftime("%H:%M:%S")
        user_message = {
            "role": "user",
            "content": prompt,
            "timestamp": timestamp
        }
        st.session_state.messages.append(user_message)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
            st.caption(f"*{timestamp}*")
        
        # Process and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = asyncio.run(process_user_message(prompt))
                
            st.markdown(response)
            
            # Add assistant message to chat
            timestamp = datetime.now().strftime("%H:%M:%S")
            assistant_message = {
                "role": "assistant",
                "content": response,
                "timestamp": timestamp
            }
            st.session_state.messages.append(assistant_message)
            st.caption(f"*{timestamp}*")

def render_sample_queries():
    """Render sample queries for users to try."""
    with st.expander("💡 Sample Queries to Try"):
        st.markdown("""
        Here are some example questions you can ask:
        
        **Database Exploration:**
        - "What databases are available?"
        - "Show me the schema of the knowledge graph"
        - "What types of entities are in the database?"
        
        **Location Queries:**
        - "What facilities are near Washington DC?"
        - "Find all military bases in Virginia"
        - "Show me airports in the northeast region"
        
        **Entity Relationships:**
        - "What is connected to the Pentagon?"
        - "Show relationships between government facilities"
        - "Find entities related to defense infrastructure"
        
        **Natural Language to SPARQL:**
        - "Convert this to SPARQL: Find all facilities with coordinates"
        - "Generate a query to find facilities by type"
        """)

def main():
    """Main application function."""
    # Initialize session state
    initialize_session_state()
    
    # Create layout
    # Sidebar for configuration and status
    render_sidebar()
    
    # Main area for chat
    col1, col2 = st.columns([3, 1])
    
    with col1:
        render_chat_interface()
    
    with col2:
        render_sample_queries()
        
        # Show conversation stats
        if st.session_state.messages:
            st.subheader("📈 Stats")
            st.metric("Messages", len(st.session_state.messages))
            st.metric("Conversation ID", st.session_state.conversation_id)
            
        # System information
        with st.expander("🔍 System Info"):
            st.write("**Configuration:**")
            st.write(f"- Model: {BEDROCK_MODEL_ID}")
            st.write(f"- Region: {AWS_REGION}")
            st.write(f"- MCP Server: {FUSEKI_MCP_SERVER_URL}")
            
            st.write("**Status:**")
            st.write(f"- Connection: {st.session_state.connection_status['status']}")
            st.write(f"- Agent: {'Ready' if st.session_state.agent_initialized else 'Not Ready'}")
    
    # Knowledge Graph Visualization Section (full width)
    render_knowledge_graph_section()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
        logger.error("Application error", error=str(e))
