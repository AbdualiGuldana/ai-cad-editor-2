from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from ai_cad_editor.inspect.summary import summarize_dxf
from ai_cad_editor.operations import core, spatial
from ai_cad_editor.operations.geometry import reconstruct_room_area


def _str_schema(description: str = "") -> types.Schema:
    return types.Schema(type="STRING", description=description)


def _num_schema(description: str = "") -> types.Schema:
    return types.Schema(type="NUMBER", description=description)


def _int_schema(description: str = "") -> types.Schema:
    return types.Schema(type="INTEGER", description=description)


def _obj(properties: dict, required: list = None) -> types.Schema:
    return types.Schema(type="OBJECT", properties=properties, required=required or [])


GEMINI_TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="list_layers",
            description="List all layers in the DXF file with their entity counts and properties.",
            parameters=_obj({}),
        ),
        types.FunctionDeclaration(
            name="find_entities_by_layer",
            description="Find all entities on a specific layer, optionally filtered by entity type.",
            parameters=_obj(
                {
                    "layer_pattern": _str_schema("Layer name or pattern to search"),
                    "entity_type": _str_schema("Optional: filter by entity type (LINE, LWPOLYLINE, TEXT, etc.)"),
                },
                required=["layer_pattern"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_entity_info",
            description="Get detailed information about a specific entity by its handle.",
            parameters=_obj({"handle": _str_schema("Entity handle (hex string)")}, required=["handle"]),
        ),
        types.FunctionDeclaration(
            name="get_area",
            description="Calculate the area of a closed entity.",
            parameters=_obj({"handle": _str_schema("Entity handle")}, required=["handle"]),
        ),
        types.FunctionDeclaration(
            name="color_layer",
            description="Change the color of all entities on a layer and save to file.",
            parameters=_obj(
                {
                    "layer_name": _str_schema(),
                    "color": _int_schema("ACI color (1=red, 2=yellow, 3=green, 4=cyan, 5=blue, 6=magenta, 7=white)"),
                    "output_path": _str_schema(),
                },
                required=["layer_name", "color", "output_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="delete_entity",
            description="Delete a specific entity and save to file.",
            parameters=_obj(
                {"handle": _str_schema(), "output_path": _str_schema()},
                required=["handle", "output_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="edit_text",
            description="Edit/rename text content of a TEXT or MTEXT entity.",
            parameters=_obj(
                {
                    "handle": _str_schema("Entity handle of TEXT/MTEXT"),
                    "new_text": _str_schema("New text content"),
                    "output_path": _str_schema("Path to save modified file"),
                },
                required=["handle", "new_text", "output_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_entity_center",
            description="Get the center point of an entity.",
            parameters=_obj({"handle": _str_schema()}, required=["handle"]),
        ),
        types.FunctionDeclaration(
            name="get_entity_bounds",
            description="Get the bounding box of an entity.",
            parameters=_obj({"handle": _str_schema()}, required=["handle"]),
        ),
        types.FunctionDeclaration(
            name="calculate_distance",
            description="Calculate distance between two entities.",
            parameters=_obj(
                {"handle1": _str_schema(), "handle2": _str_schema()},
                required=["handle1", "handle2"],
            ),
        ),
        types.FunctionDeclaration(
            name="find_entities_near_point",
            description="Find entities within a radius of a point.",
            parameters=_obj(
                {
                    "x": _num_schema(),
                    "y": _num_schema(),
                    "radius": _num_schema(),
                    "layer_pattern": _str_schema(),
                    "entity_type": _str_schema(),
                },
                required=["x", "y", "radius"],
            ),
        ),
        types.FunctionDeclaration(
            name="find_entities_in_region",
            description="Find entities in a rectangular region.",
            parameters=_obj(
                {
                    "xmin": _num_schema(),
                    "ymin": _num_schema(),
                    "xmax": _num_schema(),
                    "ymax": _num_schema(),
                    "layer_pattern": _str_schema(),
                    "entity_type": _str_schema(),
                },
                required=["xmin", "ymin", "xmax", "ymax"],
            ),
        ),
        types.FunctionDeclaration(
            name="find_entities_between",
            description="Find entities between two reference entities. CRITICAL for finding walls between rooms.",
            parameters=_obj(
                {
                    "handle1": _str_schema(),
                    "handle2": _str_schema(),
                    "layer_pattern": _str_schema(),
                    "max_distance_from_line": _num_schema(),
                },
                required=["handle1", "handle2"],
            ),
        ),
        types.FunctionDeclaration(
            name="find_adjacent_entities",
            description="Find entities near a given entity.",
            parameters=_obj(
                {
                    "handle": _str_schema(),
                    "max_distance": _num_schema(),
                    "layer_pattern": _str_schema(),
                    "entity_type": _str_schema(),
                },
                required=["handle"],
            ),
        ),
        types.FunctionDeclaration(
            name="reconstruct_room_area",
            description=(
                "Reconstruct and calculate the area of a room by tracing the smallest "
                "closed polygon of LINE wall entities enclosing a seed point (x, y) "
                "inside the room. Use this when there is no AREA-ASSIGN layer — i.e. "
                "rooms are bounded by individual LINE segments rather than closed "
                "LWPOLYLINEs. Workflow: (1) find the room label text entity, "
                "(2) call get_entity_center to get its (x, y), "
                "(3) call this function with that (x, y) and the wall layer name."
            ),
            parameters=_obj(
                {
                    "x": _num_schema("X coordinate of a point inside the room (e.g. room label center)"),
                    "y": _num_schema("Y coordinate of a point inside the room"),
                    "layer_pattern": _str_schema("Layer name containing wall LINE entities (e.g. '단면선', 'A-WALL')"),
                    "tolerance": _num_schema("Endpoint snapping tolerance in DXF units (default 10; try 50 or 100 if walls don't connect)"),
                },
                required=["x", "y"],
            ),
        ),
    ]
)


class CADAgentGemini:
    def __init__(
        self,
        dxf_path: str | Path,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
    ):
        self.dxf_path = Path(dxf_path)
        self.model_name = model

        if not self.dxf_path.exists():
            raise FileNotFoundError(f"DXF file not found: {self.dxf_path}")

        self.client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"))

        print(f"Loading DXF summary for {self.dxf_path.name}...")
        self.summary = summarize_dxf(self.dxf_path)

        self.last_output_path: Optional[str] = None
        self.system_prompt = self._build_system_prompt()

        self._config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            tools=[GEMINI_TOOLS],
        )
        self.chat_session = self.client.chats.create(
            model=self.model_name,
            config=self._config,
        )

        print(f"Agent initialized with {self.model_name}. Ready to process commands.")

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
        response = self.chat_session.send_message(user_message)

        for _ in range(max_turns):
            # Collect function calls from all parts
            function_calls = [
                part.function_call
                for part in response.candidates[0].content.parts
                if part.function_call is not None
            ]

            if not function_calls:
                # No function calls — return the text response
                return response.text

            # Execute each function call and send all results back at once
            result_parts = []
            for fn_call in function_calls:
                fn_name = fn_call.name
                fn_args = dict(fn_call.args)

                print(f"Executing: {fn_name}({json.dumps(fn_args, indent=2)})")

                result = self._execute_tool(fn_name, fn_args)

                if isinstance(result, list) and len(result) > 20:
                    result = result[:20] + [{"note": f"...{len(result)-20} more truncated"}]

                result_parts.append(
                    types.Part.from_function_response(
                        name=fn_name,
                        response={"result": json.dumps(result, default=str)},
                    )
                )

            response = self.chat_session.send_message(result_parts)

        return "Maximum turns reached."

    def reset(self):
        self.chat_session = self.client.chats.create(
            model=self.model_name,
            config=self._config,
        )
