from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import openai

from ai_cad_editor.inspect.summary import summarize_dxf
from ai_cad_editor.operations import core, spatial
from ai_cad_editor.operations.geometry import reconstruct_room_area




OPENAI_FUNCTIONS = [
    {
        "name": "list_layers",
        "description": "List all layers in the DXF file with their entity counts and properties.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "find_entities_by_layer",
        "description": "Find all entities on a specific layer, optionally filtered by entity type.",
        "parameters": {
            "type": "object",
            "properties": {
                "layer_pattern": {
                    "type": "string",
                    "description": "Layer name or pattern to search"
                },
                "entity_type": {
                    "type": "string",
                    "description": "Optional: filter by entity type (LINE, LWPOLYLINE, TEXT, etc.)"
                }
            },
            "required": ["layer_pattern"]
        }
    },
    {
        "name": "get_entity_info",
        "description": "Get detailed information about a specific entity by its handle.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "description": "Entity handle (hex string)"
                }
            },
            "required": ["handle"]
        }
    },
    {
        "name": "get_area",
        "description": "Calculate the area of a closed entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "description": "Entity handle"
                }
            },
            "required": ["handle"]
        }
    },
    {
        "name": "color_layer",
        "description": "Change the color of all entities on a layer and save to file.",
        "parameters": {
            "type": "object",
            "properties": {
                "layer_name": {"type": "string"},
                "color": {"type": "integer", "description": "ACI color (1=red, 5=blue, etc.)"},
                "output_path": {"type": "string"}
            },
            "required": ["layer_name", "color", "output_path"]
        }
    },
    {
        "name": "delete_entity",
        "description": "Delete a specific entity and save to file.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "output_path": {"type": "string"}
            },
            "required": ["handle", "output_path"]
        }
    },
    {
        "name": "edit_text",
        "description": "Edit/rename text content of a TEXT or MTEXT entity. Use to rename room labels, change annotations, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {"type": "string", "description": "Entity handle of TEXT/MTEXT"},
                "new_text": {"type": "string", "description": "New text content"},
                "output_path": {"type": "string", "description": "Path to save modified file"}
            },
            "required": ["handle", "new_text", "output_path"]
        }
    },
    {
        "name": "get_entity_center",
        "description": "Get the center point of an entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"}
            },
            "required": ["handle"]
        }
    },
    {
        "name": "get_entity_bounds",
        "description": "Get the bounding box of an entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"}
            },
            "required": ["handle"]
        }
    },
    {
        "name": "calculate_distance",
        "description": "Calculate distance between two entities.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle1": {"type": "string"},
                "handle2": {"type": "string"}
            },
            "required": ["handle1", "handle2"]
        }
    },
    {
        "name": "find_entities_near_point",
        "description": "Find entities within a radius of a point.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "radius": {"type": "number"},
                "layer_pattern": {"type": "string"},
                "entity_type": {"type": "string"}
            },
            "required": ["x", "y", "radius"]
        }
    },
    {
        "name": "find_entities_in_region",
        "description": "Find entities in a rectangular region. Use for spatial queries like 'top half'.",
        "parameters": {
            "type": "object",
            "properties": {
                "xmin": {"type": "number"},
                "ymin": {"type": "number"},
                "xmax": {"type": "number"},
                "ymax": {"type": "number"},
                "layer_pattern": {"type": "string"},
                "entity_type": {"type": "string"}
            },
            "required": ["xmin", "ymin", "xmax", "ymax"]
        }
    },
    {
        "name": "find_entities_between",
        "description": "Find entities between two reference entities. CRITICAL for finding walls between rooms.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle1": {"type": "string"},
                "handle2": {"type": "string"},
                "layer_pattern": {"type": "string"},
                "max_distance_from_line": {"type": "number"}
            },
            "required": ["handle1", "handle2"]
        }
    },
    {
        "name": "find_adjacent_entities",
        "description": "Find entities near a given entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "handle": {"type": "string"},
                "max_distance": {"type": "number"},
                "layer_pattern": {"type": "string"},
                "entity_type": {"type": "string"}
            },
            "required": ["handle"]
        }
    },
    {
        "name": "reconstruct_room_area",
        "description": (
            "Reconstruct and calculate the area of a room by tracing the smallest "
            "closed polygon of LINE wall entities enclosing a seed point (x, y) "
            "inside the room. Use this when there is no AREA-ASSIGN layer — i.e. "
            "rooms are bounded by individual LINE segments rather than closed "
            "LWPOLYLINEs. Workflow: (1) find the room label text entity, "
            "(2) call get_entity_center to get its (x, y), "
            "(3) call this function with that (x, y) and the wall layer name."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate of a point inside the room (e.g. room label center)"},
                "y": {"type": "number", "description": "Y coordinate of a point inside the room"},
                "layer_pattern": {"type": "string", "description": "Layer name containing wall LINE entities (e.g. '단면선', 'A-WALL')"},
                "tolerance": {"type": "number", "description": "Endpoint snapping tolerance in DXF units (default 10; try 50 or 100 if walls don't connect)"}
            },
            "required": ["x", "y"]
        }
    },
]


class CADAgentOpenAI:
    def __init__(
        self,
        dxf_path: str | Path, #Path to DXF file
        api_key: Optional[str] = None, #OpenAI API key (or set OPENAI_API_KEY env var)
        model: str = "gpt-4o", #Model to use (gpt-4o, gpt-4-turbo, gpt-3.5-turbo)
    ):

        self.dxf_path = Path(dxf_path)
        self.model = model

        if not self.dxf_path.exists():
            raise FileNotFoundError(f"DXF file not found: {self.dxf_path}")


        self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        print(f"Loading DXF summary for {self.dxf_path.name}...")
        self.summary = summarize_dxf(self.dxf_path)

        self.messages: List[Dict[str, Any]] = []
        self.last_output_path: Optional[str] = None

        self.system_prompt = self._build_system_prompt()
        self.messages.append({"role": "system", "content": self.system_prompt})

        print(f"Agent initialized with {self.model}. Ready to process commands.")

    def _build_system_prompt(self) -> str:
        layers_info = []
        for layer in self.summary["layers"]:
            layers_info.append(
                f"  - {layer['name']}: {layer['total_entities']} entities ({', '.join(f'{k}:{v}' for k,v in layer['entity_counts'].items())})"
            )

        text_samples = []
        for item in self.summary["text_index"]["items"][:50]:
            text_samples.append(f"  - '{item['text']}' (handle: {item['handle']}, layer: {item['layer']})")

        bbox = self.summary["drawing"]["bbox_xy"]
        bbox_str = f"[{bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}]" if bbox else "unknown"

        return f"""You are an AI assistant for editing CAD floor plans through natural language.

**File:** {self.dxf_path.name}
**Bounding Box:** {bbox_str}
**Total Entities:** {self.summary['drawing']['total_entities']}
**Layers:** {len(self.summary['layers'])} total
**Rooms:** {self.summary['boundary_candidates']['count']} boundaries

All Layers:
{chr(10).join(layers_info)}

Text Labels (sample):
{chr(10).join(text_samples)}

Guidelines:
- DXF coordinates are very large numbers (not pixels) — always use max_distance_from_line of at least 500 when calling find_entities_between
- Room labels are TEXT or MTEXT entities — find them by searching text content
- To identify which layer contains walls, look at the layer list above: wall layers are typically named A-WALL, 단면선, ELE-1, or similar structural layer names
- To find a wall between two rooms: (1) find the text handles for both room labels, (2) use find_entities_in_region on the rectangular bounding box between them on the wall layer, (3) delete each found entity
- If layers have Korean names: 벽체=wall, 마감=finish, 단면=section/cross-section, 창호=window/door, 중심선=centerline, 입면=elevation, 치수=dimension, 문=door, 창=window
- If AREA-ASSIGN layer exists: it has room boundary LWPOLYLINEs (use get_area on their handles)
- To answer "which rooms have doors/windows/X": (1) call find_entities_by_layer on the door/window layer to get all those entities, (2) for each entity call get_entity_center to get its (x,y), (3) call find_entities_near_point at that (x,y) with a large radius (try 5000–20000) on the text/label layer to find the nearest room label, (4) compile and report the full list — do NOT stop after one example, process ALL entities
- To answer "which room is biggest/smallest" when there is no AREA-ASSIGN layer: (1) find all room label text entities, (2) for each call get_entity_center, (3) call reconstruct_room_area with that center and the wall layer name, (4) sort and report all areas
- Always provide handles when identifying entities
- Think step-by-step for complex operations
- NEVER truncate or summarize lists — always show ALL results in full"""

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        tool_input = {**tool_input, "dxf_path": str(self.dxf_path)}

        try:
            # Core operations
            if tool_name == "list_layers":
                return core.list_layers(**tool_input)
            elif tool_name == "find_entities_by_layer":
                return core.find_entities_by_layer(**tool_input)
            elif tool_name == "get_entity_info":
                return core.get_entity_info(**tool_input)
            elif tool_name == "get_area":
                return core.get_area(**tool_input)
            elif tool_name == "color_layer":
                result = str(core.color_layer(**tool_input))
                self.last_output_path = tool_input.get("output_path")
                return result
            elif tool_name == "delete_entity":
                result = str(core.delete_entity(**tool_input))
                self.last_output_path = tool_input.get("output_path")
                return result
            elif tool_name == "edit_text":
                result = core.edit_text(**tool_input)
                self.last_output_path = tool_input.get("output_path")
                return result
            # Spatial operations
            elif tool_name == "get_entity_center":
                return spatial.get_entity_center(**tool_input)
            elif tool_name == "get_entity_bounds":
                return spatial.get_entity_bounds(**tool_input)
            elif tool_name == "calculate_distance":
                return spatial.calculate_distance(**tool_input)
            elif tool_name == "find_entities_near_point":
                return spatial.find_entities_near_point(**tool_input)
            elif tool_name == "find_entities_in_region":
                return spatial.find_entities_in_region(**tool_input)
            elif tool_name == "find_entities_between":
                return spatial.find_entities_between(**tool_input)
            elif tool_name == "find_adjacent_entities":
                return spatial.find_adjacent_entities(**tool_input)
            elif tool_name == "reconstruct_room_area":
                return reconstruct_room_area(**tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"error": str(e)}

    def chat(self, user_message: str, max_turns: int = 10) -> str:
        self.messages.append({"role": "user", "content": user_message})

        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1

            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                functions=OPENAI_FUNCTIONS,
                function_call="auto"
            )

            message = response.choices[0].message

            self.messages.append(message.model_dump())

            if message.function_call:
                func_name = message.function_call.name
                func_args = json.loads(message.function_call.arguments)

                print(f"Executing: {func_name}({json.dumps(func_args, indent=2)})")

                result = self._execute_tool(func_name, func_args)

                if isinstance(result, list) and len(result) > 20:
                    result = result[:20] + [{"note": f"...{len(result)-20} more truncated"}]

                self.messages.append({
                    "role": "function",
                    "name": func_name,
                    "content": json.dumps(result, indent=2)
                })

            else:
                return message.content or "No response"

        return "Maximum turns reached."

    def reset(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
