"""Core CAD editing operations for DXF files."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import ezdxf
from ezdxf.entities import DXFEntity
from ezdxf.math import Vec2


# Helper functions


def _safe_float(x: Any) -> Optional[float]:
    """Convert to float, return None if invalid or non-finite."""
    try:
        if x is None:
            return None
        v = float(x)
        if math.isfinite(v):
            return v
        return None
    except Exception:
        return None


def _entity_handle(e: DXFEntity) -> Optional[str]:
    """Get entity handle as string."""
    try:
        h = e.dxf.handle
        return str(h) if h else None
    except Exception:
        return None


def _entity_layer(e: DXFEntity) -> Optional[str]:
    """Get entity layer name."""
    try:
        return e.dxf.layer
    except Exception:
        return None


def _entity_color_raw(e: DXFEntity) -> Optional[int]:
    """Get entity ACI color number."""
    try:
        c = e.dxf.color
        return int(c) if c is not None else None
    except Exception:
        return None


def _entity_linetype(e: DXFEntity) -> Optional[str]:
    """Get entity linetype."""
    try:
        return e.dxf.linetype
    except Exception:
        return None


def _polyline_area_if_safe(e: DXFEntity) -> Optional[float]:
    """
    Calculate area for closed polylines.
    - LWPOLYLINE: uses ezdxf's get_area() (handles bulges)
    - POLYLINE: uses shoelace formula for 2D polylines
    """
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE":
            if not e.closed:
                return None

            # Try get_area() first (newer ezdxf versions)
            if hasattr(e, 'get_area') and callable(e.get_area):
                a = e.get_area()
                return float(a) if math.isfinite(a) else None

            # Fallback: manual calculation using get_points
            if hasattr(e, 'get_points'):
                points = list(e.get_points('xy'))
                if len(points) < 3:
                    return None
                # Shoelace formula
                s = 0.0
                for i in range(len(points)):
                    x1, y1 = points[i]
                    x2, y2 = points[(i + 1) % len(points)]
                    s += x1 * y2 - x2 * y1
                a = abs(s) / 2.0
                return float(a) if math.isfinite(a) else None

            return None

        if t == "POLYLINE":
            if not e.is_closed:
                return None
            # Only 2D polylines
            if getattr(e, "is_2d_polyline", False) is False and getattr(e, "is_polygon_mesh", False):
                return None

            pts2: List[Vec2] = []
            for v in e.vertices():
                p = v.dxf.location
                pts2.append(Vec2(p.x, p.y))
            if len(pts2) < 3:
                return None

            # Shoelace formula
            s = 0.0
            for i in range(len(pts2)):
                x1, y1 = pts2[i].x, pts2[i].y
                x2, y2 = pts2[(i + 1) % len(pts2)].x, pts2[(i + 1) % len(pts2)].y
                s += x1 * y2 - x2 * y1
            a = abs(s) / 2.0
            return float(a) if math.isfinite(a) else None

    except Exception:
        return None
    return None


def _hatch_area_if_safe(e: DXFEntity) -> Optional[float]:
    """Calculate area for HATCH entities if available."""
    if e.dxftype() != "HATCH":
        return None
    try:
        a = getattr(e, "area", None)
        if a is None:
            return None
        a = float(a)
        return a if math.isfinite(a) else None
    except Exception:
        return None


# Public API


def list_layers(dxf_path: str | Path) -> List[Dict[str, Any]]:
    """
    List all layers in the DXF with their properties and entity counts.

    Args:
        dxf_path: Path to input DXF file

    Returns:
        List of dicts, each containing:
        - name: Layer name
        - color: Layer ACI color
        - linetype: Layer linetype
        - is_off: Whether layer is turned off
        - is_frozen: Whether layer is frozen
        - is_locked: Whether layer is locked
        - entity_counts: Dict mapping entity type -> count
        - total_entities: Total entity count on this layer

    Example:
        layers = list_layers("sample.dxf")
        for layer in layers:
            print(f"{layer['name']}: {layer['total_entities']} entities")
    """
    doc = ezdxf.readfile(Path(dxf_path))

    # Build layer properties lookup
    layer_table: Dict[str, Any] = {}
    try:
        for layer in doc.layers:
            name = str(layer.dxf.name)
            layer_table[name] = {
                "name": name,
                "color": _safe_float(getattr(layer.dxf, "color", None)),
                "linetype": getattr(layer.dxf, "linetype", None),
                "is_off": bool(layer.is_off()),
                "is_frozen": bool(layer.is_frozen()),
                "is_locked": bool(layer.is_locked()),
            }
    except Exception:
        layer_table = {}

    # Count entities per layer
    entity_counts_by_layer: Dict[str, Dict[str, int]] = {}

    for entity in doc.modelspace():
        try:
            etype = entity.dxftype()
            layer = _entity_layer(entity) or "UNKNOWN"

            if layer not in entity_counts_by_layer:
                entity_counts_by_layer[layer] = {}

            entity_counts_by_layer[layer][etype] = (
                entity_counts_by_layer[layer].get(etype, 0) + 1
            )
        except Exception:
            continue

    # Combine into output
    layers_out: List[Dict[str, Any]] = []
    for lname, counts in sorted(entity_counts_by_layer.items(), key=lambda x: x[0].lower()):
        props = layer_table.get(lname, {"name": lname})
        layers_out.append({
            **props,
            "entity_counts": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))),
            "total_entities": int(sum(counts.values())),
        })

    return layers_out


def get_entity_info(dxf_path: str | Path, handle: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific entity by its handle.

    Args:
        dxf_path: Path to input DXF file
        handle: Entity handle (hex string like "1A2")

    Returns:
        Dict with entity properties:
        - handle: Entity handle
        - dxftype: Entity type (LINE, LWPOLYLINE, etc.)
        - layer: Layer name
        - color: ACI color number
        - linetype: Linetype name
        - (type-specific properties)

        Returns None if entity not found.

    Example:
        info = get_entity_info("sample.dxf", "1A2")
        print(f"Entity type: {info['dxftype']} on layer {info['layer']}")
    """
    doc = ezdxf.readfile(Path(dxf_path))

    try:
        entity = doc.entitydb[handle]
    except KeyError:
        return None

    try:
        info = {
            "handle": _entity_handle(entity),
            "dxftype": entity.dxftype(),
            "layer": _entity_layer(entity),
            "color": _entity_color_raw(entity),
            "linetype": _entity_linetype(entity),
        }

        # Add type-specific info
        etype = entity.dxftype()

        if etype == "LINE":
            info["start"] = list(entity.dxf.start) if hasattr(entity.dxf, "start") else None
            info["end"] = list(entity.dxf.end) if hasattr(entity.dxf, "end") else None

        elif etype in ("LWPOLYLINE", "POLYLINE"):
            info["is_closed"] = bool(getattr(entity, "closed", False) or getattr(entity, "is_closed", False))
            info["area"] = _polyline_area_if_safe(entity)

        elif etype == "CIRCLE":
            info["center"] = list(entity.dxf.center) if hasattr(entity.dxf, "center") else None
            info["radius"] = _safe_float(getattr(entity.dxf, "radius", None))

        elif etype == "TEXT":
            info["text"] = getattr(entity.dxf, "text", "")
            info["insert"] = list(entity.dxf.insert) if hasattr(entity.dxf, "insert") else None

        elif etype == "MTEXT":
            info["text"] = entity.plain_text() if hasattr(entity, "plain_text") else ""
            info["insert"] = list(entity.dxf.insert) if hasattr(entity.dxf, "insert") else None

        return info

    except Exception:
        return None


def find_entities_by_layer(
    dxf_path: str | Path,
    layer_pattern: str,
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find all entities matching a layer name pattern.

    Args:
        dxf_path: Path to input DXF file
        layer_pattern: Layer name or pattern (supports * wildcards via ezdxf query)
        entity_type: Optional filter by entity type (LINE, LWPOLYLINE, etc.)

    Returns:
        List of entity info dicts (same structure as get_entity_info)

    Example:
        # Find all entities on "WALL" layer
        walls = find_entities_by_layer("sample.dxf", "WALL")
        >>>
        # Find all LWPOLYLINEs on layers starting with "ROOM"
        rooms = find_entities_by_layer("sample.dxf", "ROOM*", entity_type="LWPOLYLINE")
    """
    doc = ezdxf.readfile(Path(dxf_path))

    # Build ezdxf query
    if entity_type:
        query = f'{entity_type}[layer=="{layer_pattern}"]'
    else:
        query = f'*[layer=="{layer_pattern}"]'

    entities = []
    try:
        for entity in doc.modelspace().query(query):
            handle = _entity_handle(entity)
            if handle:
                info = get_entity_info(dxf_path, handle)
                if info:
                    entities.append(info)
    except Exception:
        pass

    return entities


def get_area(dxf_path: str | Path, handle: str) -> Optional[float]:
    """
    Calculate the area of a closed entity (LWPOLYLINE, POLYLINE, HATCH, CIRCLE).

    Args:
        dxf_path: Path to input DXF file
        handle: Entity handle

    Returns:
        Area as float, or None if:
        - Entity not found
        - Entity is not closed
        - Area cannot be computed

    Example:
        area = get_area("sample.dxf", "1A2")
        if area:
            print(f"Room area: {area:.2f} sq units")
    """
    doc = ezdxf.readfile(Path(dxf_path))

    try:
        entity = doc.entitydb[handle]
    except KeyError:
        return None

    etype = entity.dxftype()

    # LWPOLYLINE or POLYLINE
    if etype in ("LWPOLYLINE", "POLYLINE"):
        return _polyline_area_if_safe(entity)

    # HATCH
    if etype == "HATCH":
        return _hatch_area_if_safe(entity)

    # CIRCLE
    if etype == "CIRCLE":
        try:
            r = float(entity.dxf.radius)
            return math.pi * r * r
        except Exception:
            return None

    return None


def color_layer(
    dxf_path: str | Path,
    layer_name: str,
    color: int,
    output_path: Optional[str | Path] = None,
) -> Path:
    """
    Change the color of all entities on a layer.

    Args:
        dxf_path: Path to input DXF file
        layer_name: Name of layer to recolor
        color: ACI color number (1-255, or 7 for white/black)
        output_path: Where to save modified file (default: overwrite input)

    Returns:
        Path to the saved file

    Example:
        # Make all entities on "ELECTRICAL" layer red (color 1)
        output = color_layer("sample.dxf", "ELECTRICAL", 1, "sample_modified.dxf")
        print(f"Saved to: {output}")

    Note:
        - Changes both the layer definition and individual entities
        - Creates backup is output_path not specified
        - ACI colors: 1=red, 2=yellow, 3=green, 4=cyan, 5=blue, 6=magenta, 7=white/black
    """
    doc = ezdxf.readfile(Path(dxf_path))

    # Change layer definition color
    if layer_name in doc.layers:
        layer = doc.layers.get(layer_name)
        layer.dxf.color = color

    # Change all entities on that layer
    for entity in doc.modelspace().query(f'*[layer=="{layer_name}"]'):
        try:
            entity.dxf.color = color
        except Exception:
            continue

    # Save
    out = Path(output_path) if output_path else Path(dxf_path)
    doc.saveas(out)
    return out


def delete_entity(
    dxf_path: str | Path,
    handle: str,
    output_path: Optional[str | Path] = None,
) -> Path:
    """
    Delete a specific entity from the DXF.

    Args:
        dxf_path: Path to input DXF file
        handle: Entity handle to delete
        output_path: Where to save modified file (default: overwrite input)

    Returns:
        Path to the saved file

    Raises:
        KeyError: If entity with given handle not found

    Example:
        # Delete entity with handle "1A2"
        output = delete_entity("sample.dxf", "1A2", "sample_modified.dxf")
    """
    doc = ezdxf.readfile(Path(dxf_path))

    try:
        entity = doc.entitydb[handle]
        entity.destroy()
    except KeyError:
        raise KeyError(f"Entity with handle '{handle}' not found")

    # Save
    out = Path(output_path) if output_path else Path(dxf_path)
    doc.saveas(out)
    return out


def edit_text(
    dxf_path: str | Path,
    handle: str,
    new_text: str,
    output_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    Edit the text content of a TEXT or MTEXT entity.

    Args:
        dxf_path: Path to input DXF file
        handle: Entity handle of the TEXT or MTEXT entity
        new_text: New text content to set
        output_path: Where to save modified file (default: overwrite input)

    Returns:
        Dict with:
        - success: True if text was modified
        - handle: Entity handle
        - old_text: Previous text content
        - new_text: New text content
        - output_path: Path to saved file

    Raises:
        KeyError: If entity with given handle not found
        TypeError: If entity is not a TEXT or MTEXT entity

    Example:
        # Rename room label
        result = edit_text("floor.dxf", "5660", "Room 2020", "floor_modified.dxf")
        print(f"Changed '{result['old_text']}' to '{result['new_text']}'")
    """
    doc = ezdxf.readfile(Path(dxf_path))

    try:
        entity = doc.entitydb[handle]
    except KeyError:
        raise KeyError(f"Entity with handle '{handle}' not found")

    etype = entity.dxftype()

    if etype == "TEXT":
        old_text = getattr(entity.dxf, "text", "")
        entity.dxf.text = new_text
    elif etype == "MTEXT":
        old_text = entity.plain_text() if hasattr(entity, "plain_text") else ""
        entity.text = new_text
    else:
        raise TypeError(f"Entity '{handle}' is {etype}, not TEXT or MTEXT")

    # Save
    out = Path(output_path) if output_path else Path(dxf_path)
    doc.saveas(out)

    return {
        "success": True,
        "handle": handle,
        "old_text": old_text,
        "new_text": new_text,
        "output_path": str(out),
    }
