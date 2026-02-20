# AI-Powered CAD Editor

An AI-powered natural language interface for editing DXF/DWG architectural floor plans. This tool enables architects to query, analyze, and modify CAD files using AI request commands.

## Features

### Inspect: DXF Parsing and Summarization
- Parse DXF files and extract structured metadata
- Generate JSON summaries with layers, entities, text labels, and room boundaries
- For now, it support common entity types like LINE, LWPOLYLINE, TEXT, MTEXT, HATCH, CIRCLE

### Operations: CAD Operations
- **Core**: List layers, find entities by layer, get entity info, calculate areas, change layer colors, delete entities, edit/rename text
- **Spatial**: Find entities near points, in regions, between rooms, adjacent entities

### Agent: AI Agent with Natural Language
- Natural language interface using OpenAI GPT-4 or Claude
- 14 tool functions for CAD control
- Spatial reasoning for complex queries

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/ai-cad-editor-2.git
cd ai-cad-editor-2

# Create virtual environment
python -m venv venv
source venv/bin/activate 

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### 1. Set up API Key
```bash
export OPENAI_API_KEY="your-api-key"
# Or for Claude:
#export ANTHROPIC_API_KEY="your-api-key"
```

### 2. Run the Demo -> for now just like this simple ddemo
```bash
python demo_phase3.py
```

### 3. Try Commands
```
You: How many layers are in this file?
You: What is the area of room E201?
You: Change all doors to red
You: Rename room 201 to 2020
You: Delete the wall between two bathrooms
```

#It also gives u back the changed DXF file -> please, compare witht he original version for the correctness

## Project Structure

```
ai-cad-editor/
├── ai_cad_editor/
│   ├── inspect/          # Phase 1: DXF parsing
│   │   └── summary.py
│   ├── operations/       # Phase 2: CAD operations
│   │   ├── core.py       # Basic operations
│   │   └── spatial.py    # Spatial analysis
│   └── agent/            # Phase 3: AI agents
│       ├── cad_agent_claude.py    # Claude agent
│       ├── cad_agent_openai.py   # OpenAI agent
│       └── tools.py              # Tool definitions
├── examples/
│   ├── dxf_files/        # Sample DXF files
│   └── demo_*.py         # Demo scripts
├── tests/                # Unit tests
├── docs/                 # Documentation
├── demo_phase3.py        # Main demo script
└── requirements.txt
```

## Available Tools (14 total)

| Tool | Description |
|------|-------------|
| `list_layers` | List all layers with entity counts |
| `find_entities_by_layer` | Find entities on a specific layer |
| `get_entity_info` | Get detailed info about an entity |
| `get_area` | Calculate area of closed entities |
| `color_layer` | Change color of all entities on a layer |
| `delete_entity` | Delete a specific entity |
| `edit_text` | Edit/rename TEXT or MTEXT entities |
| `get_entity_center` | Get centroid of an entity |
| `get_entity_bounds` | Get bounding box of an entity |
| `calculate_distance` | Calculate distance between entities |
| `find_entities_near_point` | Find entities within radius |
| `find_entities_in_region` | Find entities in rectangular area |
| `find_entities_between` | Find entities between two references |
| `find_adjacent_entities` | Find neighboring entities |

## Example Usage

```python
from ai_cad_editor.agent import CADAgentOpenAI

# Initialize agent with DXF file
agent = CADAgentOpenAI("floor_plan.dxf")

# Natural language commands
response = agent.chat("List all layers")
print(response)

response = agent.chat("What's the area of room 201?")
print(response)

response = agent.chat("Change the door layer to blue")
print(response)
```

## Requirements

- Python 3.9+
- ezdxf >= 1.0.0
- openai >= 1.0.0 (for OpenAI agent)
- anthropic >= 0.40.0 (for Claude agent)

