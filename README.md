# AI CAD Editor

A natural language interface for editing DXF/DWG architectural floor plans. Supports querying, analyzing, and modifying CAD files through conversational commands.

## Features

- Parse DXF files and extract structured metadata (layers, entities, text labels, room boundaries)
- Core operations: list layers, find entities, calculate areas, change colors, delete entities, edit text
- Spatial queries: find entities near points, in regions, between rooms, adjacent entities
- Geometry: reconstruct room boundaries and calculate areas from raw LINE wall segments
- Natural language interface using OpenAI GPT-4o or Google Gemini
- Supports Korean DXF files with automatic layer name translation
- Streamlit web UI with side-by-side Before / After SVG viewer

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/ai-cad-editor-2.git
cd ai-cad-editor-2

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

Run the CLI demo:
```bash
python demo_phase3.py
```

Run the web UI:
```bash
streamlit run app.py
```


API keys — create `.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "your-openai-key"
GEMINI_API_KEY = "your-gemini-key"
```

Example commands:
```
List all layers
What is the area of room E201?
Change all doors to red
Rename room 201 to Conference Room
Which rooms have doors?
Which room is the biggest?
```

## Project Structure

```
ai-cad-editor-2/
├── ai_cad_editor/
│   ├── inspect/
│   ├── operations/
│   └── agent/
├── examples/
│   ├── dxf_files/
│   └── dxf_files_korean/
├── app.py
├── demo_phase3.py
└── requirements.txt
```

## Requirements

- Python 3.9+
- ezdxf >= 1.0.0
- openai >= 1.0.0
- google-genai >= 1.0.0
- streamlit >= 1.30.0
