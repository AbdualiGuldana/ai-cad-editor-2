from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic

from ai_cad_editor.inspect.summary import summarize_dxf
from ai_cad_editor.operations import core, spatial
from ai_cad_editor.agent.tools import TOOLS


class CADAgent:
    def __init__(
        self,
        dxf_path: str | Path, #Path to DXF file to work with
        api_key: Optional[str] = None, #Anthropic API key (or set ANTHROPIC_API_KEY env var)
        model: str = "claude-sonnet-4-20250514", #Claude model to use 
    ):
        self.dxf_path = Path(dxf_path)
        self.model = model

        if not self.dxf_path.exists():
            raise FileNotFoundError(f"DXF file not found: {self.dxf_path}")

        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

        # load DXF summary
        print(f"Loading DXF summary for {self.dxf_path.name}...")
        self.summary = summarize_dxf(self.dxf_path)

        # Conversation history
        self.messages: List[Dict[str, Any]] = []

        # System prompt
        self.system_prompt = self._build_system_prompt()

        print(f"Agent is ready to process commands.")

    def _build_system_prompt(self) -> str:

        layers_info = []
        for layer in self.summary["layers"][:10]:  # Top 10 layers
            layers_info.append(
                f"  - {layer['name']}: {layer['total_entities']} entities "
                f"(types: {', '.join(list(layer['entity_counts'].keys())[:3])})"
            )

        text_samples = []
        for item in self.summary["text_index"]["items"][:10]:
            text_samples.append(f"  - '{item['text']}' (handle: {item['handle']})")

        bbox = self.summary["drawing"]["bbox_xy"]
        bbox_str = f"[{bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}]" if bbox else "unknown"

        return f"""You are an AI assistant that helps architects edit CAD floor plans through natural language.

You have access to a DXF file with the following structure:

**File:** {self.dxf_path.name}
**Bounding Box (xmin, ymin, xmax, ymax):** {bbox_str}
**Total Entities:** {self.summary['drawing']['total_entities']}

**Layers ({len(self.summary['layers'])} total):**
{chr(10).join(layers_info)}

**Text Labels ({self.summary['text_index']['count']} total, sample):**
{chr(10).join(text_samples)}

**Boundary Candidates:** {self.summary['boundary_candidates']['count']} closed polylines/hatches (potential rooms)

**Your Capabilities:**
1. **Query Information:** List layers, find entities, calculate areas
2. **Spatial Analysis:** Find entities near points, in regions, between entities
3. **Modify CAD:** Delete entities, change colors, edit/rename text, save modifications

**Important Guidelines:**
- When user mentions spatial location (top, bottom, left, right), use find_entities_in_region with the bounding box
- When user wants to merge/connect rooms, find walls using find_entities_between
- Room labels are TEXT/MTEXT entities, room boundaries are LWPOLYLINE on layers like "AREA-ASSIGN"
- Wall entities are typically LINE/LWPOLYLINE on layers like "A-WALL"
- Always provide handles when you identify entities so user can reference them
- When modifying files, use descriptive output paths like "floor_plan_modified.dxf"

**Workflow for Complex Operations:**
1. Understand user intent
2. Find relevant entities using spatial and layer queries
3. Analyze spatial relationships if needed
4. Perform operations (delete, modify, etc.)
5. Report results clearly with entity handles and areas

Be concise but informative. Think step-by-step for complex requests.
"""

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
                return str(core.color_layer(**tool_input))
            elif tool_name == "delete_entity":
                return str(core.delete_entity(**tool_input))
            elif tool_name == "edit_text":
                return core.edit_text(**tool_input)

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

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": str(e)}

    def chat(self, user_message: str, max_turns: int = 10) -> str:
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                tools=TOOLS,
                messages=self.messages
            )

            self.messages.append({
                "role": "assistant",
                "content": response.content
            })

            if response.stop_reason == "end_turn":
                text_blocks = [block.text for block in response.content if block.type == "text"]
                return "\n".join(text_blocks)

            elif response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        print(f"Executing: {block.name}({json.dumps(block.input, indent=2)})")

                        result = self._execute_tool(block.name, block.input)

                        if isinstance(result, list) and len(result) > 20:
                            result = result[:20] + [{"note": f"... {len(result) - 20} more items truncated"}]

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, indent=2)
                        })

                self.messages.append({
                    "role": "user",
                    "content": tool_results
                })

            else:
                return f"Unexpected stop reason: {response.stop_reason}"

        return "Maximum turns reached. The request may be too complex."

    def reset(self):
        self.messages = []
