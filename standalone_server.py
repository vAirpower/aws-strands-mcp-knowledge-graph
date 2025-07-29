"""
Standalone HTTP MCP Server with In-Memory RDF Store

This server provides HTTP endpoints for MCP functionality using an in-memory RDF store.
No external dependencies like Fuseki required.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
import traceback
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for request/response
class InitializeRequest(BaseModel):
    protocol_version: str = Field(default="1.0")
    client_info: Dict[str, Any] = Field(default_factory=dict)

class ToolCallRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)

class ToolResponse(BaseModel):
    content: List[Dict[str, Any]]
    isError: bool = False

class ToolInfo(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class ToolsResponse(BaseModel):
    tools: List[ToolInfo]

class StandaloneMCPServer:
    """
    Standalone HTTP MCP server with in-memory RDF store.
    
    Provides REST endpoints that expose MCP functionality over HTTP using rdflib.
    """
    
    def __init__(self):
        """Initialize the standalone MCP server."""
        self.app = FastAPI(
            title="Standalone MCP Server",
            description="HTTP-enabled MCP server with in-memory RDF store",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # CORS middleware for cross-origin requests
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Initialize in-memory RDF graph
        self.graph = Graph()
        self.initialized = False
        
        # Setup routes
        self._setup_routes()
        
        # Setup error handlers
        self._setup_error_handlers()
        
        # Load sample data
        self._load_sample_data()
        
    def _load_sample_data(self):
        """Load GEOINT sample data into the in-memory graph."""
        try:
            # Define namespaces
            GEOINT = Namespace("http://example.org/geoint/")
            GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
            
            # Add sample GEOINT data
            facilities = [
                {
                    "id": "pentagon",
                    "name": "The Pentagon",
                    "type": "Government Building",
                    "lat": 38.8719,
                    "lon": -77.0563,
                    "state": "Virginia",
                    "city": "Arlington"
                },
                {
                    "id": "white_house",
                    "name": "White House",
                    "type": "Government Building", 
                    "lat": 38.8977,
                    "lon": -77.0365,
                    "state": "Washington DC",
                    "city": "Washington"
                },
                {
                    "id": "andrews_afb",
                    "name": "Joint Base Andrews",
                    "type": "Military Base",
                    "lat": 38.7681,
                    "lon": -76.8690,
                    "state": "Maryland",
                    "city": "Andrews"
                },
                {
                    "id": "quantico",
                    "name": "Marine Corps Base Quantico", 
                    "type": "Military Base",
                    "lat": 38.5221,
                    "lon": -77.3411,
                    "state": "Virginia",
                    "city": "Quantico"
                },
                {
                    "id": "dca_airport",
                    "name": "Ronald Reagan Washington National Airport",
                    "type": "Airport",
                    "lat": 38.8512,
                    "lon": -77.0402,
                    "state": "Virginia", 
                    "city": "Arlington"
                },
                {
                    "id": "iad_airport",
                    "name": "Washington Dulles International Airport",
                    "type": "Airport",
                    "lat": 38.9531,
                    "lon": -77.4565,
                    "state": "Virginia",
                    "city": "Dulles"
                },
                {
                    "id": "bwi_airport", 
                    "name": "Baltimore/Washington International Airport",
                    "type": "Airport",
                    "lat": 39.1774,
                    "lon": -76.6684,
                    "state": "Maryland",
                    "city": "Baltimore"
                },
                {
                    "id": "norfolk_nb",
                    "name": "Naval Station Norfolk",
                    "type": "Military Base",
                    "lat": 36.9467,
                    "lon": -76.2929,
                    "state": "Virginia",
                    "city": "Norfolk"
                },
                {
                    "id": "fort_belvoir",
                    "name": "Fort Belvoir",
                    "type": "Military Base", 
                    "lat": 38.7034,
                    "lon": -77.1364,
                    "state": "Virginia",
                    "city": "Fort Belvoir"
                },
                {
                    "id": "capitol_building",
                    "name": "United States Capitol",
                    "type": "Government Building",
                    "lat": 38.8899,
                    "lon": -77.0091,
                    "state": "Washington DC",
                    "city": "Washington"
                }
            ]
            
            for facility in facilities:
                facility_uri = GEOINT[facility["id"]]
                
                # Add basic properties
                self.graph.add((facility_uri, RDF.type, GEOINT.Facility))
                self.graph.add((facility_uri, RDFS.label, Literal(facility["name"])))
                self.graph.add((facility_uri, GEOINT.facilityType, Literal(facility["type"])))
                self.graph.add((facility_uri, GEOINT.state, Literal(facility["state"])))
                self.graph.add((facility_uri, GEOINT.city, Literal(facility["city"])))
                
                # Add geographic coordinates
                self.graph.add((facility_uri, GEO.lat, Literal(facility["lat"])))
                self.graph.add((facility_uri, GEO.long, Literal(facility["lon"])))
                
                # Add ID for easy reference
                self.graph.add((facility_uri, GEOINT.facilityId, Literal(facility["id"])))
            
            logger.info(f"Loaded {len(facilities)} facilities into in-memory RDF store")
            logger.info(f"Total triples in graph: {len(self.graph)}")
            
        except Exception as e:
            logger.error(f"Failed to load sample data: {str(e)}")
        
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "mcp_initialized": self.initialized,
                "rdf_triples": len(self.graph),
                "store_type": "in-memory"
            }
        
        @self.app.post("/initialize")
        async def initialize(request: InitializeRequest):
            """Initialize the MCP server."""
            try:
                self.initialized = True
                
                logger.info(f"MCP server initialized with {len(self.graph)} RDF triples")
                
                return {
                    "protocol_version": request.protocol_version,
                    "server_info": {
                        "name": "standalone-mcp-server",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {},
                        "resources": {}
                    }
                }
                
            except Exception as e:
                logger.error(f"Failed to initialize MCP server: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")
        
        @self.app.get("/tools", response_model=ToolsResponse)
        async def list_tools():
            """List all available MCP tools."""
            try:
                tools_info = [
                    ToolInfo(
                        name="execute_sparql",
                        description="Execute a SPARQL query against the in-memory RDF store",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "SPARQL query to execute"}
                            },
                            "required": ["query"]
                        }
                    ),
                    ToolInfo(
                        name="count_triples",
                        description="Count the total number of triples in the RDF store",
                        inputSchema={
                            "type": "object",
                            "properties": {}
                        }
                    ),
                    ToolInfo(
                        name="get_classes",
                        description="Get all classes (rdf:type) in the RDF store",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "description": "Maximum number of classes to return", "default": 100}
                            }
                        }
                    ),
                    ToolInfo(
                        name="get_properties",
                        description="Get all properties used in the RDF store",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "description": "Maximum number of properties to return", "default": 100}
                            }
                        }
                    ),
                    ToolInfo(
                        name="search_by_text",
                        description="Search for entities containing specific text",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "Text to search for"},
                                "limit": {"type": "integer", "description": "Maximum number of results to return", "default": 50}
                            },
                            "required": ["text"]
                        }
                    ),
                    ToolInfo(
                        name="get_sample_data",
                        description="Get a sample of data from the RDF store",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "description": "Maximum number of triples to return", "default": 10}
                            }
                        }
                    ),
                    ToolInfo(
                        name="get_facilities_near",
                        description="Get facilities near a specific location",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "location": {"type": "string", "description": "Location name (e.g., 'Washington DC', 'Virginia')"},
                                "facility_type": {"type": "string", "description": "Optional facility type filter"},
                                "limit": {"type": "integer", "description": "Maximum number of results", "default": 20}
                            },
                            "required": ["location"]
                        }
                    )
                ]
                
                logger.info(f"Listed {len(tools_info)} MCP tools")
                return ToolsResponse(tools=tools_info)
                
            except Exception as e:
                logger.error(f"Failed to list tools: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")
        
        @self.app.post("/tools/{tool_name}", response_model=ToolResponse)
        async def call_tool(tool_name: str, request: ToolCallRequest):
            """Call a specific MCP tool."""
            try:
                logger.info(f"Calling tool: {tool_name} with args: {request.arguments}")
                
                # Route to appropriate tool handler
                if tool_name == "execute_sparql":
                    result = await self._execute_sparql(request.arguments)
                elif tool_name == "count_triples":
                    result = await self._count_triples(request.arguments)
                elif tool_name == "get_classes":
                    result = await self._get_classes(request.arguments)
                elif tool_name == "get_properties":
                    result = await self._get_properties(request.arguments)
                elif tool_name == "search_by_text":
                    result = await self._search_by_text(request.arguments)
                elif tool_name == "get_sample_data":
                    result = await self._get_sample_data(request.arguments)
                elif tool_name == "get_facilities_near":
                    result = await self._get_facilities_near(request.arguments)
                else:
                    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
                
                return ToolResponse(content=result, isError=False)
                
            except Exception as e:
                logger.error(f"Tool call failed: {tool_name}, error: {str(e)}", exc_info=True)
                return ToolResponse(
                    content=[{
                        "type": "text",
                        "text": f"Error executing tool '{tool_name}': {str(e)}"
                    }],
                    isError=True
                )
    
    async def _execute_sparql(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a SPARQL query."""
        query = args.get("query", "")
        if not query.strip():
            raise ValueError("Query cannot be empty")
        
        try:
            # Execute query against in-memory graph
            results = self.graph.query(query)
            
            # Format results for display
            if hasattr(results, 'vars') and results.vars:
                # SELECT query
                headers = [str(var) for var in results.vars]
                rows = []
                for row in results:
                    formatted_row = []
                    for value in row:
                        if value:
                            formatted_row.append(str(value))
                        else:
                            formatted_row.append("")
                    rows.append(formatted_row)
                
                if rows:
                    table_text = f"Query Results ({len(rows)} rows):\n\n"
                    table_text += " | ".join(headers) + "\n"
                    table_text += "-" * (len(" | ".join(headers))) + "\n"
                    for row in rows[:20]:  # Limit to first 20 rows
                        table_text += " | ".join(row) + "\n"
                    
                    if len(rows) > 20:
                        table_text += f"... and {len(rows) - 20} more rows\n"
                    
                    return [{"type": "text", "text": table_text}]
                else:
                    return [{"type": "text", "text": "Query executed successfully but returned no results."}]
            else:
                # Other types of queries (ASK, CONSTRUCT, etc.)
                result_count = len(list(results))
                return [{"type": "text", "text": f"Query executed successfully. Results: {result_count}"}]
                
        except Exception as e:
            raise Exception(f"SPARQL query failed: {str(e)}")
    
    async def _count_triples(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Count total triples in the RDF store."""
        count = len(self.graph)
        return [{"type": "text", "text": f"Total triples in RDF store: {count}"}]
    
    async def _get_classes(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all classes in the RDF store."""
        limit = args.get("limit", 100)
        
        query = f"""
        SELECT DISTINCT ?class (COUNT(?instance) as ?count) WHERE {{
            ?instance a ?class .
        }}
        GROUP BY ?class
        ORDER BY DESC(?count)
        LIMIT {limit}
        """
        
        results = self.graph.query(query)
        
        if results:
            text = f"Classes in RDF store:\n\n"
            for row in results:
                class_uri = str(row[0])
                count = str(row[1]) if row[1] else "0"
                text += f"• {class_uri} ({count} instances)\n"
            return [{"type": "text", "text": text}]
        
        return [{"type": "text", "text": "No classes found"}]
    
    async def _get_properties(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all properties in the RDF store."""
        limit = args.get("limit", 100)
        
        query = f"""
        SELECT DISTINCT ?property (COUNT(*) as ?count) WHERE {{
            ?s ?property ?o .
        }}
        GROUP BY ?property
        ORDER BY DESC(?count)
        LIMIT {limit}
        """
        
        results = self.graph.query(query)
        
        if results:
            text = f"Properties in RDF store:\n\n"
            for row in results:
                prop_uri = str(row[0])
                count = str(row[1]) if row[1] else "0"
                text += f"• {prop_uri} (used {count} times)\n"
            return [{"type": "text", "text": text}]
        
        return [{"type": "text", "text": "No properties found"}]
    
    async def _search_by_text(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for entities containing specific text."""
        search_text = args.get("text", "")
        limit = args.get("limit", 50)
        
        if not search_text:
            raise ValueError("Search text cannot be empty")
        
        query = f"""
        SELECT DISTINCT ?subject ?predicate ?object WHERE {{
            ?subject ?predicate ?object .
            FILTER(contains(lcase(str(?object)), lcase("{search_text}")))
        }}
        LIMIT {limit}
        """
        
        results = self.graph.query(query)
        result_list = list(results)
        
        if result_list:
            text = f"Search results for '{search_text}' ({len(result_list)} found):\n\n"
            for row in result_list:
                subject = str(row[0])
                predicate = str(row[1])
                obj = str(row[2])
                text += f"• {subject} → {predicate} → {obj}\n"
            return [{"type": "text", "text": text}]
        
        return [{"type": "text", "text": f"No results found for '{search_text}'"}]
    
    async def _get_sample_data(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get sample data from the RDF store."""
        limit = args.get("limit", 10)
        
        query = f"""
        SELECT ?subject ?predicate ?object WHERE {{
            ?subject ?predicate ?object .
        }}
        LIMIT {limit}
        """
        
        results = self.graph.query(query)
        result_list = list(results)
        
        if result_list:
            text = f"Sample data from RDF store ({len(result_list)} triples):\n\n"
            for row in result_list:
                subject = str(row[0])
                predicate = str(row[1])
                obj = str(row[2])
                text += f"• {subject} → {predicate} → {obj}\n"
            return [{"type": "text", "text": text}]
        
        return [{"type": "text", "text": "No sample data available"}]
    
    async def _get_facilities_near(self, args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get facilities near a specific location."""
        location = args.get("location", "")
        facility_type = args.get("facility_type", "")
        limit = args.get("limit", 20)
        
        if not location:
            raise ValueError("Location cannot be empty")
        
        # Build query based on parameters
        filter_clauses = []
        
        # Location filter (search in state or city)
        filter_clauses.append(f"""
            (contains(lcase(str(?state)), lcase("{location}")) || 
             contains(lcase(str(?city)), lcase("{location}")) ||
             contains(lcase(str(?name)), lcase("{location}")))
        """)
        
        # Facility type filter if provided
        if facility_type:
            filter_clauses.append(f'contains(lcase(str(?type)), lcase("{facility_type}"))')
        
        filter_clause = "FILTER(" + " && ".join(filter_clauses) + ")"
        
        query = f"""
        PREFIX geoint: <http://example.org/geoint/>
        PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?facility ?name ?type ?state ?city ?lat ?lon WHERE {{
            ?facility a geoint:Facility ;
                     rdfs:label ?name ;
                     geoint:facilityType ?type ;
                     geoint:state ?state ;
                     geoint:city ?city ;
                     geo:lat ?lat ;
                     geo:long ?lon .
            {filter_clause}
        }}
        ORDER BY ?name
        LIMIT {limit}
        """
        
        results = self.graph.query(query)
        result_list = list(results)
        
        if result_list:
            text = f"Facilities near '{location}':\n\n"
            if facility_type:
                text = f"Facilities of type '{facility_type}' near '{location}':\n\n"
            
            for row in result_list:
                name = str(row[1])
                ftype = str(row[2])
                state = str(row[3])
                city = str(row[4])
                lat = str(row[5])
                lon = str(row[6])
                
                text += f"📍 **{name}**\n"
                text += f"   Type: {ftype}\n"
                text += f"   Location: {city}, {state}\n"
                text += f"   Coordinates: {lat}, {lon}\n\n"
                
            return [{"type": "text", "text": text}]
        
        return [{"type": "text", "text": f"No facilities found near '{location}'"}]
    
    def _setup_error_handlers(self):
        """Setup global error handlers."""
        
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            """Handle unexpected exceptions."""
            logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
            
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error": str(exc),
                    "timestamp": datetime.now().isoformat()
                }
            )

def start_server():
    """Function to start the server (called by the demo runner)."""
    # Create server instance
    server = StandaloneMCPServer()
    
    # Configuration
    host = os.getenv("HTTP_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("HTTP_MCP_PORT", "8000"))
    
    logger.info(f"Starting Standalone MCP Server on {host}:{port}")
    logger.info(f"RDF triples loaded: {len(server.graph)}")
    
    # Run the server
    uvicorn.run(
        server.app,
        host=host,
        port=port,
        log_level="info"
    )

# Global server instance
server = StandaloneMCPServer()

# FastAPI app instance for external access
app = server.app

async def main():
    """Main function to run the server."""
    start_server()

if __name__ == "__main__":
    start_server()
