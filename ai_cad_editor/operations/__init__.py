"""CAD editing operations for DXF files."""

from ai_cad_editor.operations.core import (
    list_layers,
    get_entity_info,
    find_entities_by_layer,
    get_area,
    color_layer,
    delete_entity,
    edit_text,
)

from ai_cad_editor.operations.spatial import (
    get_entity_center,
    get_entity_bounds,
    calculate_distance,
    find_entities_near_point,
    find_entities_in_region,
    find_entities_between,
    find_adjacent_entities,
)

__all__ = [
    # Core operations
    "list_layers",
    "get_entity_info",
    "find_entities_by_layer",
    "get_area",
    "color_layer",
    "delete_entity",
    "edit_text",
    # Spatial operations
    "get_entity_center",
    "get_entity_bounds",
    "calculate_distance",
    "find_entities_near_point",
    "find_entities_in_region",
    "find_entities_between",
    "find_adjacent_entities",
]
