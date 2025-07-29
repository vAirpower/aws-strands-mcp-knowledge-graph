"""
Graph Visualizer Module

Provides knowledge graph visualization capabilities for the Stardog MCP integration.
Parses RDF data from MCP tool responses and creates interactive graph visualizations.
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from urllib.parse import urlparse
import networkx as nx
import pandas as pd
import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class Triple:
    """Represents an RDF triple (subject, predicate, object)."""
    subject: str
    predicate: str
    object: str
    
    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))

@dataclass
class GraphContext:
    """Context information for graph generation."""
    user_query: str
    query_entities: Set[str]
    tool_results: List[Dict[str, Any]]
    relevant_triples: List[Triple]

class RDFTripleParser:
    """Parses RDF triples from various MCP tool response formats."""
    
    def __init__(self):
        self.namespace_prefixes = {
            "http://example.org/geoint/": "geoint:",
            "http://www.w3.org/2003/01/geo/wgs84_pos#": "geo:",
            "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
            "http://www.w3.org/2002/07/owl#": "owl:"
        }
    
    def parse_mcp_response(self, response_data: Dict[str, Any]) -> List[Triple]:
        """
        Parse MCP tool response to extract RDF triples.
        
        Args:
            response_data: Response from MCP tool call
            
        Returns:
            List of extracted triples
        """
        triples = []
        
        try:
            # Handle different response formats
            if "content" in response_data:
                content_items = response_data["content"]
                for item in content_items:
                    if item.get("type") == "text":
                        text_content = item.get("text", "")
                        triples.extend(self._parse_text_content(text_content))
            
            # Direct text parsing if response is a string
            elif isinstance(response_data, str):
                triples.extend(self._parse_text_content(response_data))
                
        except Exception as e:
            logger.error("Error parsing MCP response", error=str(e))
            
        return triples
    
    def _parse_text_content(self, text: str) -> List[Triple]:
        """Parse text content to extract RDF-like relationships."""
        triples = []
        
        try:
            # Pattern 1: SPARQL query results table format
            table_triples = self._parse_sparql_table(text)
            triples.extend(table_triples)
            
            # Pattern 2: Facility information format
            facility_triples = self._parse_facility_info(text)
            triples.extend(facility_triples)
            
            # Pattern 3: Direct triple format (subject → predicate → object)
            arrow_triples = self._parse_arrow_format(text)
            triples.extend(arrow_triples)
            
            # Pattern 4: Strands agent format [subject] ----predicate----> [object]
            strands_triples = self._parse_strands_format(text)
            triples.extend(strands_triples)
            
            # Pattern 5: Natural language entity mentions
            entity_triples = self._parse_entity_mentions(text)
            triples.extend(entity_triples)
            
        except Exception as e:
            logger.error("Error parsing text content", error=str(e))
            
        return triples
    
    def _parse_sparql_table(self, text: str) -> List[Triple]:
        """Parse SPARQL query results in table format."""
        triples = []
        
        # Look for table-like structures with | separators
        lines = text.split('\n')
        headers = []
        
        for i, line in enumerate(lines):
            if '|' in line and not line.strip().startswith('-'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                
                if i == 0 or not headers:
                    # This might be headers
                    if any(header in parts for header in ['subject', 'predicate', 'object', 'facility', 'name', 'type']):
                        headers = parts
                        continue
                
                # This is data
                if len(parts) >= 3 and headers:
                    if 'subject' in headers and 'predicate' in headers and 'object' in headers:
                        try:
                            subj_idx = headers.index('subject') if 'subject' in headers else 0
                            pred_idx = headers.index('predicate') if 'predicate' in headers else 1
                            obj_idx = headers.index('object') if 'object' in headers else 2
                            
                            subject = parts[subj_idx] if subj_idx < len(parts) else ""
                            predicate = parts[pred_idx] if pred_idx < len(parts) else ""
                            obj = parts[obj_idx] if obj_idx < len(parts) else ""
                            
                            if subject and predicate and obj:
                                triples.append(Triple(
                                    subject=self._clean_uri(subject),
                                    predicate=self._clean_uri(predicate),
                                    object=self._clean_uri(obj)
                                ))
                        except (IndexError, ValueError):
                            continue
        
        return triples
    
    def _parse_facility_info(self, text: str) -> List[Triple]:
        """Parse facility information format from MCP responses."""
        triples = []
        
        # Pattern: 📍 **Facility Name**
        #          Type: Military Base
        #          Location: City, State
        #          Coordinates: lat, lon
        
        facility_blocks = re.split(r'📍\s*\*\*([^*]+)\*\*', text)
        
        for i in range(1, len(facility_blocks), 2):
            if i + 1 < len(facility_blocks):
                facility_name = facility_blocks[i].strip()
                facility_info = facility_blocks[i + 1]
                
                facility_uri = self._create_facility_uri(facility_name)
                
                # Add basic facility triple
                triples.append(Triple(
                    subject=facility_uri,
                    predicate="rdf:type",
                    object="geoint:Facility"
                ))
                
                triples.append(Triple(
                    subject=facility_uri,
                    predicate="rdfs:label",
                    object=f'"{facility_name}"'
                ))
                
                # Parse details
                for line in facility_info.split('\n'):
                    line = line.strip()
                    if line.startswith('Type:'):
                        facility_type = line.replace('Type:', '').strip()
                        triples.append(Triple(
                            subject=facility_uri,
                            predicate="geoint:facilityType",
                            object=f'"{facility_type}"'
                        ))
                    
                    elif line.startswith('Location:'):
                        location = line.replace('Location:', '').strip()
                        # Parse "City, State" format
                        if ',' in location:
                            city, state = [x.strip() for x in location.split(',', 1)]
                            triples.append(Triple(
                                subject=facility_uri,
                                predicate="geoint:city",
                                object=f'"{city}"'
                            ))
                            triples.append(Triple(
                                subject=facility_uri,
                                predicate="geoint:state",
                                object=f'"{state}"'
                            ))
                    
                    elif line.startswith('Coordinates:'):
                        coords = line.replace('Coordinates:', '').strip()
                        # Parse "lat, lon" format
                        if ',' in coords:
                            try:
                                lat, lon = [x.strip() for x in coords.split(',', 1)]
                                triples.append(Triple(
                                    subject=facility_uri,
                                    predicate="geo:lat",
                                    object=lat
                                ))
                                triples.append(Triple(
                                    subject=facility_uri,
                                    predicate="geo:long",
                                    object=lon
                                ))
                            except ValueError:
                                continue
        
        return triples
    
    def _parse_arrow_format(self, text: str) -> List[Triple]:
        """Parse direct triple format: subject → predicate → object."""
        triples = []
        
        # Find lines with → arrows
        lines = [line.strip() for line in text.split('\n') if '→' in line]
        
        for line in lines:
            if line.startswith('•'):
                line = line[1:].strip()
            
            parts = [p.strip() for p in line.split('→')]
            if len(parts) == 3:
                subject, predicate, obj = parts
                triples.append(Triple(
                    subject=self._clean_uri(subject),
                    predicate=self._clean_uri(predicate),
                    object=self._clean_uri(obj)
                ))
                
        return triples
    
    def _parse_strands_format(self, text: str) -> List[Triple]:
        """Parse Strands agent format: [subject] ----predicate----> [object]."""
        triples = []
        
        # Pattern to match [entity] ----predicate----> [entity]
        pattern = r'\[([^\]]+)\]\s*----([^-]+)-+>\s*\[([^\]]+)\]'
        matches = re.findall(pattern, text)
        
        for match in matches:
            subject, predicate, obj = match
            subject = subject.strip()
            predicate = predicate.strip()
            obj = obj.strip()
            
            if subject and predicate and obj:
                triples.append(Triple(
                    subject=self._create_entity_uri(subject),
                    predicate=f"geoint:{predicate}",
                    object=self._create_entity_uri(obj)
                ))
        
        # Also look for nested properties like [----city---->[Arlington]
        property_pattern = r'\[\s*----([^-]+)-+>\s*\[([^\]]+)\]\s*'
        property_matches = re.findall(property_pattern, text)
        
        # We need context to know what entity these properties belong to
        # Look for the pattern where properties follow facility blocks
        lines = text.split('\n')
        current_entity = None
        
        for line in lines:
            line = line.strip()
            
            # Check if this line defines a main entity
            main_entity_match = re.search(r'\[([^\]]+)\]\s*----([^-]+)-+>\s*\[([^\]]+)\]', line)
            if main_entity_match:
                current_entity = main_entity_match.group(1).strip()
                continue
            
            # Check if this line has a property for the current entity
            if current_entity:
                prop_match = re.search(r'\[\s*----([^-]+)-+>\s*\[([^\]]+)\]\s*', line)
                if prop_match:
                    prop_name = prop_match.group(1).strip()
                    prop_value = prop_match.group(2).strip()
                    
                    triples.append(Triple(
                        subject=self._create_entity_uri(current_entity),
                        predicate=f"geoint:{prop_name}",
                        object=f'"{prop_value}"'
                    ))
        
        return triples
    
    def _create_entity_uri(self, name: str) -> str:
        """Create a URI for an entity name."""
        # Handle common entity mappings
        entity_mappings = {
            "Pentagon": "geoint:pentagon",
            "Andrews AFB": "geoint:andrews_afb", 
            "Norfolk NB": "geoint:norfolk_nb",
            "Fort Meade": "geoint:fort_meade",
            "White House": "geoint:white_house",
            "Government Building": "geoint:government_building",
            "Military Base": "geoint:military_base",
            "USA": "geoint:usa",
            "Virginia": "geoint:virginia",
            "Maryland": "geoint:maryland",
            "Arlington": "geoint:arlington",
            "Camp Springs": "geoint:camp_springs",
            "Norfolk": "geoint:norfolk",
            "Fort Meade": "geoint:fort_meade_city"
        }
        
        if name in entity_mappings:
            return entity_mappings[name]
        
        # Create generic URI
        uri_part = re.sub(r'[^a-zA-Z0-9\s]', '', name)
        uri_part = re.sub(r'\s+', '_', uri_part.strip()).lower()
        return f"geoint:{uri_part}"
    
    def _parse_entity_mentions(self, text: str) -> List[Triple]:
        """Parse entity mentions and create implicit relationships."""
        triples = []
        
        # Common facility names and types from the GEOINT data
        facilities = {
            "Pentagon": "geoint:pentagon",
            "White House": "geoint:white_house", 
            "Joint Base Andrews": "geoint:andrews_afb",
            "Quantico": "geoint:quantico",
            "DCA Airport": "geoint:dca_airport",
            "Dulles": "geoint:iad_airport",
            "BWI": "geoint:bwi_airport",
            "Norfolk": "geoint:norfolk_nb",
            "Fort Belvoir": "geoint:fort_belvoir",
            "Capitol": "geoint:capitol_building"
        }
        
        locations = {
            "Washington DC": "geoint:washington_dc",
            "Virginia": "geoint:virginia",
            "Maryland": "geoint:maryland",
            "Arlington": "geoint:arlington"
        }
        
        # Find mentioned entities
        mentioned_facilities = set()
        mentioned_locations = set()
        
        text_lower = text.lower()
        
        for name, uri in facilities.items():
            if name.lower() in text_lower:
                mentioned_facilities.add((name, uri))
                
        for name, uri in locations.items():
            if name.lower() in text_lower:
                mentioned_locations.add((name, uri))
        
        # Create triples for mentioned entities
        for name, uri in mentioned_facilities:
            triples.append(Triple(
                subject=uri,
                predicate="rdf:type",
                object="geoint:Facility"
            ))
            triples.append(Triple(
                subject=uri,
                predicate="rdfs:label",
                object=f'"{name}"'
            ))
            
        for name, uri in mentioned_locations:
            triples.append(Triple(
                subject=uri,
                predicate="rdf:type", 
                object="geoint:Location"
            ))
            triples.append(Triple(
                subject=uri,
                predicate="rdfs:label",
                object=f'"{name}"'
            ))
        
        return triples
    
    def _create_facility_uri(self, name: str) -> str:
        """Create a URI for a facility name."""
        # Convert name to URI-friendly format
        uri_part = re.sub(r'[^a-zA-Z0-9\s]', '', name)
        uri_part = re.sub(r'\s+', '_', uri_part.strip()).lower()
        return f"geoint:{uri_part}"
    
    def _clean_uri(self, uri: str) -> str:
        """Clean and normalize URIs."""
        uri = uri.strip()
        
        # Remove quotes
        if uri.startswith('"') and uri.endswith('"'):
            uri = uri[1:-1]
        
        # Apply namespace prefixes
        for full_ns, prefix in self.namespace_prefixes.items():
            if uri.startswith(full_ns):
                uri = uri.replace(full_ns, prefix)
                break
        
        return uri

class KnowledgeGraphBuilder:
    """Builds NetworkX graphs from RDF triples."""
    
    def __init__(self):
        self.parser = RDFTripleParser()
    
    def build_graph_from_mcp_responses(self, tool_results: List[Dict[str, Any]]) -> nx.Graph:
        """
        Build a knowledge graph from MCP tool responses.
        
        Args:
            tool_results: List of MCP tool call results
            
        Returns:
            NetworkX graph representation
        """
        all_triples = []
        
        # Parse all tool results
        for result in tool_results:
            triples = self.parser.parse_mcp_response(result)
            all_triples.extend(triples)
        
        # Build NetworkX graph
        return self.build_graph_from_triples(all_triples)
    
    def build_graph_from_triples(self, triples: List[Triple]) -> nx.Graph:
        """Build NetworkX graph from RDF triples."""
        graph = nx.Graph()
        
        # Add nodes and edges
        for triple in triples:
            # Add subject and object as nodes
            graph.add_node(triple.subject)
            graph.add_node(triple.object)
            
            # Add edge with predicate as edge attribute
            graph.add_edge(
                triple.subject,
                triple.object,
                predicate=triple.predicate,
                label=self._format_predicate_label(triple.predicate)
            )
        
        # Enrich nodes with additional attributes
        self._enrich_nodes(graph, triples)
        
        return graph
    
    def _enrich_nodes(self, graph: nx.Graph, triples: List[Triple]):
        """Add additional attributes to nodes based on triples."""
        
        # Collect node attributes
        node_attributes = {}
        
        for triple in triples:
            subject = triple.subject
            predicate = triple.predicate
            obj = triple.object
            
            # Initialize attributes if not present
            if subject not in node_attributes:
                node_attributes[subject] = {
                    'label': self._extract_node_label(subject),
                    'type': 'Unknown',
                    'properties': {}
                }
            
            # Set node type based on rdf:type
            if predicate == 'rdf:type':
                node_attributes[subject]['type'] = self._format_type_label(obj)
            
            # Set label based on rdfs:label
            elif predicate == 'rdfs:label':
                clean_label = obj.strip('"')
                node_attributes[subject]['label'] = clean_label
            
            # Store other properties
            else:
                node_attributes[subject]['properties'][predicate] = obj
        
        # Apply attributes to graph nodes
        for node_id, attrs in node_attributes.items():
            if node_id in graph:
                graph.nodes[node_id].update(attrs)
    
    def _extract_node_label(self, uri: str) -> str:
        """Extract a human-readable label from a URI."""
        if ':' in uri:
            return uri.split(':', 1)[1].replace('_', ' ').title()
        return uri
    
    def _format_type_label(self, type_uri: str) -> str:
        """Format type URI into readable label."""
        if ':' in type_uri:
            return type_uri.split(':', 1)[1].replace('_', ' ').title()
        return type_uri
        
    def _format_predicate_label(self, predicate: str) -> str:
        """Format predicate into readable label."""
        if ':' in predicate:
            label = predicate.split(':', 1)[1]
        else:
            label = predicate
            
        # Handle common predicates
        label_map = {
            'type': 'is a',
            'label': 'named',
            'facilityType': 'type',
            'state': 'in state',
            'city': 'in city',
            'lat': 'latitude',
            'long': 'longitude'
        }
        
        return label_map.get(label, label.replace('_', ' ').title())

class GraphVisualizer:
    """Creates interactive graph visualizations using Streamlit-Agraph."""
    
    def __init__(self):
        self.node_colors = {
            'Facility': '#FF6B6B',      # Red for facilities
            'Location': '#4ECDC4',      # Teal for locations  
            'Government Building': '#45B7D1',  # Blue for government
            'Military Base': '#96CEB4',  # Green for military
            'Airport': '#FFEAA7',       # Yellow for airports
            'Unknown': '#DDA0DD'        # Purple for unknown
        }
        
        self.node_sizes = {
            'Facility': 25,
            'Location': 20,
            'Government Building': 30,
            'Military Base': 28,
            'Airport': 26,
            'Unknown': 20
        }
    
    def create_agraph_nodes_edges(self, graph: nx.Graph) -> Tuple[List[Node], List[Edge]]:
        """Convert NetworkX graph to Streamlit-Agraph format."""
        nodes = []
        edges = []
        
        # Create nodes
        for node_id in graph.nodes():
            node_data = graph.nodes[node_id]
            
            node_type = node_data.get('type', 'Unknown')
            node_label = node_data.get('label', node_id)
            
            color = self.node_colors.get(node_type, self.node_colors['Unknown'])
            size = self.node_sizes.get(node_type, self.node_sizes['Unknown'])
            
            # Create tooltip with additional info
            properties = node_data.get('properties', {})
            tooltip_parts = [f"Type: {node_type}"]
            
            for prop, value in properties.items():
                if prop not in ['rdf:type', 'rdfs:label']:
                    clean_prop = prop.split(':')[-1].replace('_', ' ').title()
                    clean_value = str(value).strip('"')
                    tooltip_parts.append(f"{clean_prop}: {clean_value}")
            
            tooltip = "\n".join(tooltip_parts)
            
            nodes.append(Node(
                id=node_id,
                label=node_label,
                size=size,
                color=color,
                title=tooltip
            ))
        
        # Create edges  
        for source, target, edge_data in graph.edges(data=True):
            edge_label = edge_data.get('label', edge_data.get('predicate', ''))
            
            edges.append(Edge(
                source=source,
                target=target,
                label=edge_label,
                color='#888888',
                width=2
            ))
        
        return nodes, edges
    
    def render_interactive_graph(
        self,
        graph: nx.Graph,
        height: int = 500,
        physics_enabled: bool = True
    ) -> Any:
        """Render interactive graph using Streamlit-Agraph."""
        
        if len(graph.nodes()) == 0:
            st.warning("No graph data to display")
            return None
        
        # Convert to agraph format
        nodes, edges = self.create_agraph_nodes_edges(graph)
        
        # Configure graph appearance
        config = Config(
            width=750,
            height=height,
            directed=False,
            physics=physics_enabled,
            hierarchical=False,
            node={'labelProperty': 'label'},
            edge={'labelProperty': 'label'},
        )
        
        # Render graph
        return agraph(nodes=nodes, edges=edges, config=config)

class GraphContextExtractor:
    """Extracts relevant graph context from user queries and agent responses."""
    
    def __init__(self):
        self.parser = RDFTripleParser()
        
    def extract_query_context(
        self,
        user_query: str,
        agent_response: str,
        tool_results: List[Dict[str, Any]]
    ) -> GraphContext:
        """
        Extract graph context from user interaction.
        
        Args:
            user_query: User's original question
            agent_response: Agent's response text
            tool_results: Results from MCP tool calls
            
        Returns:
            Graph context with relevant entities and triples
        """
        
        # Extract query entities
        query_entities = self._extract_query_entities(user_query)
        
        # Parse all tool results to get triples
        all_triples = []
        for result in tool_results:
            triples = self.parser.parse_mcp_response(result)
            all_triples.extend(triples)
        
        # Filter relevant triples
        relevant_triples = self._filter_relevant_triples(all_triples, query_entities, user_query)
        
        return GraphContext(
            user_query=user_query,
            query_entities=query_entities,
            tool_results=tool_results,
            relevant_triples=relevant_triples
        )
    
    def _extract_query_entities(self, query: str) -> Set[str]:
        """Extract entity names mentioned in the user query."""
        entities = set()
        
        # Common entity patterns
        entity_patterns = {
            r'\b(?:washington\s*dc?|district\s*of\s*columbia)\b': 'Washington DC',
            r'\bvirginia\b': 'Virginia',
            r'\bmaryland\b': 'Maryland',  
            r'\bpentagon\b': 'Pentagon',
            r'\bwhite\s*house\b': 'White House',
            r'\bandrews\b': 'Joint Base Andrews',
            r'\bquantico\b': 'Quantico',
            r'\bdca\b': 'DCA Airport',
            r'\bdulles\b': 'Dulles',
            r'\bbwi\b': 'BWI',
            r'\bnorfolk\b': 'Norfolk',
            r'\bcapitol\b': 'Capitol',
            r'\bmilitary\s*base': 'Military Base',
            r'\bairport': 'Airport',
            r'\bgovernment\s*building': 'Government Building'
        }
        
        query_lower = query.lower()
        
        for pattern, entity in entity_patterns.items():
            if re.search(pattern, query_lower):
                entities.add(entity)
        
        return entities
    
    def _filter_relevant_triples(
        self,
        triples: List[Triple],
        query_entities: Set[str],
        user_query: str
    ) -> List[Triple]:
        """Filter triples to show only those relevant to the query."""
        
        if not query_entities:
            # If no specific entities found, return all triples
            return triples
        
        relevant_triples = []
        relevant_uris = set()
        
        # First pass: find triples with direct entity matches
        for triple in triples:
            for entity in query_entities:
                entity_lower = entity.lower()
                
                # Check if entity appears in any part of the triple
                if (entity_lower in triple.subject.lower() or
                    entity_lower in triple.object.lower() or
                    entity_lower.replace(' ', '_') in triple.subject.lower() or
                    entity_lower.replace(' ', '_') in triple.object.lower()):
                    
                    relevant_triples.append(triple)
                    relevant_uris.add(triple.subject)
                    relevant_uris.add(triple.object)
                    break
        
        # Second pass: find connected triples (one hop away)
        for triple in triples:
            if (triple.subject in relevant_uris or triple.object in relevant_uris) and triple not in relevant_triples:
                relevant_triples.append(triple)
        
        return relevant_triples

# Main interface functions
def create_knowledge_graph_from_mcp_results(tool_results: List[Dict[str, Any]]) -> nx.Graph:
    """Create a knowledge graph from MCP tool results."""
    builder = KnowledgeGraphBuilder()
    return builder.build_graph_from_mcp_responses(tool_results)

def extract_graph_context_from_interaction(
    user_query: str,
    agent_response: str, 
    tool_results: List[Dict[str, Any]]
) -> GraphContext:
    """Extract graph context from user interaction."""
    extractor = GraphContextExtractor()
    return extractor.extract_query_context(user_query, agent_response, tool_results)

def render_knowledge_graph(
    graph: nx.Graph,
    height: int = 500,
    physics_enabled: bool = True
) -> Any:
    """Render an interactive knowledge graph."""
    visualizer = GraphVisualizer()
    return visualizer.render_interactive_graph(graph, height, physics_enabled)
