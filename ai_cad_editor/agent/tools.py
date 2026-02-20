TOOLS = [
    {
        "name": "list_layers",
        "description": "List all layers in the DXF file with their entity counts and properties.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "find_entities_by_layer",
        "description": "Find all entities on a specific layer, optionally filtered by entity type (LINE, LWPOLYLINE, TEXT, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "layer_pattern": {
                    "type": "string",
                    "description": "Layer name or pattern to search"
                },
                "entity_type": {
                    "type": "string",
                    "description": "Optional: filter by entity type (LINE, LWPOLYLINE, TEXT, MTEXT, HATCH, etc.)"
                }
            },
            "required": ["layer_pattern"]
        }
    },
    {
        "name": "get_entity_info",
        "description": "Get detailed information about a specific entity by its handle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "description": "Entity handle (hex string like '88F')"
                }
            },
            "required": ["handle"]
        }
    },
    {
        "name": "get_area",
        "description": "Calculate the area of a closed entity (LWPOLYLINE, POLYLINE, HATCH, CIRCLE).",
        "input_schema": {
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
        "description": "Change the color of all entities on a layer. Saves to output file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "layer_name": {
                    "type": "string",
                    "description": "Layer name to recolor"
                },
                "color": {
                    "type": "integer",
                    "description": "ACI color number (1=red, 2=yellow, 3=green, 4=cyan, 5=blue, 6=magenta, 7=white/black)"
                },
                "output_path": {
                    "type": "string",
                    "description": "Path to save modified DXF file"
                }
            },
            "required": ["layer_name", "color", "output_path"]
        }
    },
    {
        "name": "delete_entity",
        "description": "Delete a specific entity from the DXF. Saves to output file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "description": "Entity handle to delete"
                },
                "output_path": {
                    "type": "string",
                    "description": "Path to save modified DXF file"
                }
            },
            "required": ["handle", "output_path"]
        }
    },
    {
        "name": "edit_text",
        "description": "Edit/rename text content of a TEXT or MTEXT entity. Use this to rename room labels, change annotations, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "description": "Entity handle of the TEXT or MTEXT entity to edit"
                },
                "new_text": {
                    "type": "string",
                    "description": "New text content to set"
                },
                "output_path": {
                    "type": "string",
                    "description": "Path to save modified DXF file"
                }
            },
            "required": ["handle", "new_text", "output_path"]
        }
    },
    # Spatial analysis tools
    {
        "name": "get_entity_center",
        "description": "Get the center point (centroid) of an entity as (x, y) coordinates.",
        "input_schema": {
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
        "name": "get_entity_bounds",
        "description": "Get the bounding box of an entity (xmin, ymin, xmax, ymax, width, height, center).",
        "input_schema": {
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
        "name": "calculate_distance",
        "description": "Calculate the distance between the centers of two entities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle1": {
                    "type": "string",
                    "description": "First entity handle"
                },
                "handle2": {
                    "type": "string",
                    "description": "Second entity handle"
                }
            },
            "required": ["handle1", "handle2"]
        }
    },
    {
        "name": "find_entities_near_point",
        "description": "Find all entities within a radius of a specific point. Useful for finding entities near a location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {
                    "type": "number",
                    "description": "X coordinate of center point"
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate of center point"
                },
                "radius": {
                    "type": "number",
                    "description": "Search radius"
                },
                "layer_pattern": {
                    "type": "string",
                    "description": "Optional: filter by layer"
                },
                "entity_type": {
                    "type": "string",
                    "description": "Optional: filter by entity type"
                }
            },
            "required": ["x", "y", "radius"]
        }
    },
    {
        "name": "find_entities_in_region",
        "description": "Find all entities within a rectangular region. Useful for finding entities in a specific area (top, bottom, left, right of floor plan).",
        "input_schema": {
            "type": "object",
            "properties": {
                "xmin": {"type": "number", "description": "Left edge of region"},
                "ymin": {"type": "number", "description": "Bottom edge of region"},
                "xmax": {"type": "number", "description": "Right edge of region"},
                "ymax": {"type": "number", "description": "Top edge of region"},
                "layer_pattern": {
                    "type": "string",
                    "description": "Optional: filter by layer"
                },
                "entity_type": {
                    "type": "string",
                    "description": "Optional: filter by entity type"
                }
            },
            "required": ["xmin", "ymin", "xmax", "ymax"]
        }
    },
    {
        "name": "find_entities_between",
        "description": "Find entities spatially between two reference entities. CRITICAL for finding walls between rooms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle1": {
                    "type": "string",
                    "description": "First entity handle (e.g., first room)"
                },
                "handle2": {
                    "type": "string",
                    "description": "Second entity handle (e.g., second room)"
                },
                "layer_pattern": {
                    "type": "string",
                    "description": "Optional: filter by layer (e.g., 'A-WALL' for walls)"
                },
                "max_distance_from_line": {
                    "type": "number",
                    "description": "Maximum perpendicular distance from centerline (default: 100)"
                }
            },
            "required": ["handle1", "handle2"]
        }
    },
    {
        "name": "find_adjacent_entities",
        "description": "Find entities adjacent to (near) a given entity. Useful for finding neighboring rooms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "handle": {
                    "type": "string",
                    "description": "Reference entity handle"
                },
                "max_distance": {
                    "type": "number",
                    "description": "Maximum distance to consider adjacent (default: 200)"
                },
                "layer_pattern": {
                    "type": "string",
                    "description": "Optional: filter by layer"
                },
                "entity_type": {
                    "type": "string",
                    "description": "Optional: filter by entity type"
                }
            },
            "required": ["handle"]
        }
    },
]
