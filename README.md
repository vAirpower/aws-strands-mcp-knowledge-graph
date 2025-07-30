# AWS Strands Agent with MCP Knowledge Graph Proof of Concept (Text-to-SPARQL/STARDOG)
<img width="2523" height="1536" alt="Screenshot 2025-07-29 at 4 50 29 PM" src="https://github.com/user-attachments/assets/b8ee6f95-9dc3-4efd-88a9-e33f2ff67aba" />



[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.47+-red.svg)](https://streamlit.io/)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-orange.svg)](https://aws.amazon.com/bedrock/)
[![MCP](https://img.shields.io/badge/Protocol-MCP-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> PoC-ready Streamlit application featuring AWS Strands Agents, Model Context Protocol (MCP) server integration, and interactive knowledge graph visualization with Claude 3.7 Sonnet.

## 🌟 Features

- **🤖 AWS Strands Agent**: Autonomous reasoning with Claude 3.7 Sonnet via AWS Bedrock
- **📊 Interactive Knowledge Graph**: Real-time graph visualization with streamlit-agraph
- **🔗 MCP Integration**: 7 specialized tools for SPARQL queries and semantic search
- **⚡ In-Memory RDF Store**: 80+ triples of GEOINT data for demo purposes
- **🎯 One-Command Launch**: Single script starts both MCP server and Streamlit app
- **🔐 Security First**: Environment-based configuration with no hardcoded credentials

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- AWS Account with Bedrock access
- AWS CLI configured with appropriate permissions

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/vAirpower/aws-strands-mcp-knowledge-graph.git
   cd aws-strands-mcp-knowledge-graph
   ```

2. **Set up environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure AWS credentials**
   ```bash
   # Option 1: AWS CLI
   aws configure
   
   # Option 2: Environment variables
   export AWS_ACCESS_KEY_ID=your_key_here
   export AWS_SECRET_ACCESS_KEY=your_secret_here
   export AWS_REGION=us-east-1
   
   # Option 3: Copy and edit environment file
   cp .env.example .env
   # Edit .env with your actual AWS credentials
   ```

4. **Launch the application**
   ```bash
   python run_demo.py
   ```

5. **Access the demo**
   - **Streamlit App**: http://localhost:8501
   - **MCP Server Health**: http://localhost:8000/health

## 💬 Sample Queries

Try these example queries in the Streamlit interface:

- "What facilities are near Washington DC?"
- "Find all military bases in Virginia"
- "Tell me about the Pentagon"
- "Show me airports and their locations"
- "What types of facilities do we have data for?"

## 🏗️ Architecture

The application consists of three main components:

```
┌─────────────────────┐    HTTP    ┌─────────────────────┐
│   Streamlit App     │◄──────────►│   MCP Server        │
│   (Port 8501)       │            │   (Port 8000)       │
└─────────────────────┘            └─────────────────────┘
           │                                  │
           │                                  │
           ▼                                  ▼
┌─────────────────────┐            ┌─────────────────────┐
│   AWS Strands       │            │   In-Memory RDF     │
│   Agent             │            │   Store (80 triples)│
│   (Claude 3.7)      │            │                     │
└─────────────────────┘            └─────────────────────┘
           │
           ▼
┌─────────────────────┐
│   AWS Bedrock       │
│   API               │
└─────────────────────┘
```

### Component Details

- **Streamlit App** (`app.py`): Interactive web interface with graph visualization
- **MCP Server** (`standalone_server.py`): HTTP server providing 7 specialized tools
- **Strands Agent** (`strands_agent.py`): AWS Bedrock integration with Claude 3.7 Sonnet
- **Graph Visualizer** (`graph_visualizer.py`): Interactive network graph rendering
- **MCP Client** (`mcp_http_client.py`): HTTP client for MCP communication

## 🛠️ Available MCP Tools

The MCP server provides 7 specialized tools:

1. **execute_sparql**: Execute SPARQL queries against the RDF store
2. **get_facilities_near**: Find facilities within proximity of coordinates
3. **search_by_text**: Text-based search across facility descriptions
4. **get_sample_data**: Retrieve sample RDF data for exploration
5. **get_classes**: List all RDF classes in the knowledge graph
6. **get_properties**: List all RDF properties in the knowledge graph
7. **count_triples**: Get total count of RDF triples

## 📁 Project Structure

```
aws-strands-mcp-knowledge-graph/
├── README.md                 # This file
├── LICENSE                   # MIT license
├── .gitignore               # Git ignore rules
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
├── run_demo.py             # Main launcher script
├── app.py                  # Streamlit application
├── standalone_server.py    # MCP server
├── strands_agent.py        # AWS Strands Agent
├── mcp_http_client.py      # MCP HTTP client
└── graph_visualizer.py     # Graph visualization
```

## ⚙️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here

# MCP Server Configuration
MCP_SERVER_URL=http://localhost:8000
MCP_SERVER_PORT=8000

# Streamlit Configuration
STREAMLIT_PORT=8501
STREAMLIT_HOST=localhost

# Agent Configuration
BEDROCK_MODEL_ID=anthropic.claude-3-7-sonnet-20250219-v1:0
AGENT_MAX_ITERATIONS=10
AGENT_TIMEOUT=30
```

### AWS Bedrock Setup

1. **Enable Claude 3.7 Sonnet** in your AWS Bedrock console
2. **Set up IAM permissions** for Bedrock access:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel",
           "bedrock:InvokeModelWithResponseStream"
         ],
         "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-7-sonnet-*"
       }
     ]
   }
   ```

## 🔧 Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/ -v --cov=.
```

### Code Formatting
```bash
# Install formatting tools
pip install black isort mypy

# Format code
black .
isort .

# Type checking
mypy . --ignore-missing-imports
```

### Local Development
```bash
# Run MCP server only
python standalone_server.py

# Run Streamlit app only (requires MCP server running)
streamlit run app.py --server.port 8501
```

## 🐳 Docker Support

### Build and Run
```bash
# Build image
docker build -t aws-strands-mcp .

# Run container
docker run -p 8501:8501 -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_REGION=us-east-1 \
  aws-strands-mcp
```

### Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📊 Knowledge Graph Data

The demo includes 80+ RDF triples representing GEOINT facilities:

- **Military Bases**: Pentagon, Joint Base Andrews, etc.
- **Airports**: Reagan National, Dulles International, etc.
- **Government Facilities**: White House, Capitol Building, etc.
- **Geographic Coordinates**: Latitude/longitude for all facilities
- **Relationships**: Facility types, locations, and connections

### Sample RDF Data
```turtle
@prefix geo: <http://www.w3.org/2003/01/geo/wgs84_pos#> .
@prefix facility: <http://example.org/facility/> .

facility:pentagon a facility:MilitaryBase ;
    rdfs:label "Pentagon" ;
    geo:lat 38.8719 ;
    geo:long -77.0563 ;
    facility:location "Arlington, Virginia" .
```

## 🔍 Troubleshooting

### Common Issues

1. **AWS Credentials Not Found**
   ```bash
   # Verify AWS credentials
   aws sts get-caller-identity
   
   # Or check environment variables
   echo $AWS_ACCESS_KEY_ID
   ```

2. **MCP Server Connection Failed**
   ```bash
   # Check MCP server health
   curl http://localhost:8000/health
   
   # Restart MCP server
   python standalone_server.py
   ```

3. **Streamlit App Won't Start**
   ```bash
   # Check port availability
   lsof -i :8501
   
   # Run with different port
   streamlit run app.py --server.port 8502
   ```

4. **Graph Visualization Issues**
   ```bash
   # Clear browser cache
   # Refresh page
   # Check browser console for errors
   ```

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export DEBUG_MODE=true
python run_demo.py
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Format code: `black . && isort .`
6. Commit changes: `git commit -m 'Add amazing feature'`
7. Push to branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **AWS Bedrock** team for Claude 3.7 Sonnet integration
- **Model Context Protocol** for the MCP specification
- **Streamlit** community for the visualization framework
- **Open source contributors** who made this project possible

## 📞 Support

- 💬 **Discussions**: [GitHub Discussions](https://github.com/vAirpower/aws-strands-mcp-knowledge-graph/discussions)
- 🐛 **Issues**: [GitHub Issues](https://github.com/vAirpower/aws-strands-mcp-knowledge-graph/issues)
- 📧 **Email**: [support@vairpower.com](mailto:support@vairpower.com)

## 🔗 Related Projects

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [SPARQL Query Language](https://www.w3.org/TR/sparql11-query/)

---

**⭐ Star this repo if you find it useful!**

Made with ❤️ by Adam Bluhm
