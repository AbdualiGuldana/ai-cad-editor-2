"""Spatial analysis and search operations for DXF files."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import ezdxf
from ezdxf.entities import DXFEntity
from ezdxf.math import Vec2

from ai_cad_editor.operations.core import (
    _entity_handle,
    _entity_layer,
    get_entity_info,
)


# Helper functions

def _get_center_from_entity(entity: DXFEntity) -> Optional[Tuple[float, float]]:
    """Get center point directly from an entity object."""
    try:
        etype = entity.dxftype()

        if etype in ("TEXT", "MTEXT"):
            insert = entity.dxf.insert
            return (float(insert[0]), float(insert[1]))

        if etype == "LWPOLYLINE":
            if hasattr(entity, 'get_points'):
                points = list(entity.get_points('xy'))
                if points:
                    x_sum = sum(p[0] for p in points)
                    y_sum = sum(p[1] for p in points)
                    return (x_sum / len(points), y_sum / len(points))

        if etype == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            return ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)

        if etype == "CIRCLE":
            center = entity.dxf.center
            return (float(center[0]), float(center[1]))

        return None
    except Exception:
        return None


def _extract_entity_info(entity: DXFEntity) -> Dict[str, Any]:
    """Extract basic info directly from an entity object."""
    info = {
        'handle': entity.dxf.handle,
        'dxftype': entity.dxftype(),
        'layer': entity.dxf.layer,
    }

    try:
        info['color'] = entity.dxf.color
    except Exception:
        info['color'] = None

    try:
        info['linetype'] = entity.dxf.linetype
    except Exception:
        info['linetype'] = None

    return info


# Public API

def get_entity_center(dxf_path: str | Path, handle: str) -> Optional[Tuple[float, float]]:
    """
    Get the center point (centroid) of an entity.

    Args:
        dxf_path: Path to DXF file
        handle: Entity handle

    Returns:
        (x, y) tuple of center point, or None if unable to calculate
    """
    doc = ezdxf.readfile(Path(dxf_path))

    try:
        entity = doc.entitydb[handle]
    except KeyError:
        return None

    return _get_center_from_entity(entity)


def get_entity_bounds(dxf_path: str | Path, handle: str) -> Optional[Dict[str, float]]:
    """
    Get bounding box of an entity.

    Args:
        dxf_path: Path to DXF file
        handle: Entity handle

    Returns:
        Dict with keys: xmin, ymin, xmax, ymax, width, height, center_x, center_y
        Or None if unable to calculate
    """
    doc = ezdxf.readfile(Path(dxf_path))

    try:
        entity = doc.entitydb[handle]
    except KeyError:
        return None

    etype = entity.dxftype()

    try:
        if etype == "LWPOLYLINE":
            if hasattr(entity, 'get_points'):
                points = list(entity.get_points('xy'))
                if points:
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    xmin, xmax = min(xs), max(xs)
                    ymin, ymax = min(ys), max(ys)
                    return {
                        "xmin": xmin,
                        "ymin": ymin,
                        "xmax": xmax,
                        "ymax": ymax,
                        "width": xmax - xmin,
                        "height": ymax - ymin,
                        "center_x": (xmin + xmax) / 2,
                        "center_y": (ymin + ymax) / 2,
                    }

        if etype == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            xmin = min(start[0], end[0])
            xmax = max(start[0], end[0])
            ymin = min(start[1], end[1])
            ymax = max(start[1], end[1])
            return {
                "xmin": xmin,
                "ymin": ymin,
                "xmax": xmax,
                "ymax": ymax,
                "width": xmax - xmin,
                "height": ymax - ymin,
                "center_x": (xmin + xmax) / 2,
                "center_y": (ymin + ymax) / 2,
            }

        return None

    except Exception:
        return None


def calculate_distance(
    dxf_path: str | Path,
    handle1: str,
    handle2: str,
) -> Optional[float]:
    """
    Calculate distance between centers of two entities.

    Args:
        dxf_path: Path to DXF file
        handle1: First entity handle
        handle2: Second entity handle

    Returns:
        Distance in drawing units, or None if unable to calculate
    """
    center1 = get_entity_center(dxf_path, handle1)
    center2 = get_entity_center(dxf_path, handle2)

    if center1 is None or center2 is None:
        return None

    dx = center2[0] - center1[0]
    dy = center2[1] - center1[1]
    return math.sqrt(dx * dx + dy * dy)


def find_entities_near_point(
    dxf_path: str | Path,
    x: float,
    y: float,
    radius: float,
    layer_pattern: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find all entities within a radius of a point.

    Args:
        dxf_path: Path to DXF file
        x: X coordinate of center point
        y: Y coordinate of center point
        radius: Search radius
        layer_pattern: Optional layer filter
        entity_type: Optional entity type filter

    Returns:
        List of entity info dicts with added 'distance' and 'center' keys,
        sorted by distance (closest first)
    """
    doc = ezdxf.readfile(Path(dxf_path))
    msp = doc.modelspace()

    results = []
    target = Vec2(x, y)

    if layer_pattern and entity_type:
        query = f'{entity_type}[layer=="{layer_pattern}"]'
    elif entity_type:
        query = entity_type
    elif layer_pattern:
        query = f'*[layer=="{layer_pattern}"]'
    else:
        query = '*'

    for entity in msp.query(query):
        try:
            center = _get_center_from_entity(entity)
            if not center:
                continue

            entity_pos = Vec2(center[0], center[1])
            distance = entity_pos.distance(target)

            if distance <= radius:
                info = _extract_entity_info(entity)
                info['distance'] = float(distance)
                info['center'] = center
                results.append(info)
        except Exception:
            continue

    results.sort(key=lambda x: x['distance'])
    return results


def find_entities_in_region(
    dxf_path: str | Path,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    layer_pattern: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find all entities within a rectangular region.

    Args:
        dxf_path: Path to DXF file
        xmin, ymin: Bottom-left corner of region
        xmax, ymax: Top-right corner of region
        layer_pattern: Optional layer filter
        entity_type: Optional entity type filter

    Returns:
        List of entity info dicts with added 'center' key
    """
    doc = ezdxf.readfile(Path(dxf_path))
    msp = doc.modelspace()

    results = []

    if layer_pattern and entity_type:
        query = f'{entity_type}[layer=="{layer_pattern}"]'
    elif entity_type:
        query = entity_type
    elif layer_pattern:
        query = f'*[layer=="{layer_pattern}"]'
    else:
        query = '*'

    for entity in msp.query(query):
        try:
            center = _get_center_from_entity(entity)
            if not center:
                continue

            cx, cy = center
            if xmin <= cx <= xmax and ymin <= cy <= ymax:
                info = _extract_entity_info(entity)
                info['center'] = center
                results.append(info)
        except Exception:
            continue

    return results


def find_entities_between(
    dxf_path: str | Path,
    handle1: str,
    handle2: str,
    layer_pattern: Optional[str] = None,
    max_distance_from_line: float = 100.0,
) -> List[Dict[str, Any]]:
    """
    Find entities spatially between two entities.

    Finds entities whose centers lie in a corridor between the two
    reference entities. Useful for finding walls between rooms.

    Args:
        dxf_path: Path to DXF file
        handle1: First entity handle
        handle2: Second entity handle
        layer_pattern: Optional layer filter (e.g., "A-WALL" for walls)
        max_distance_from_line: Max perpendicular distance from centerline

    Returns:
        List of entity info dicts sorted by distance to centerline
    """
    center1 = get_entity_center(dxf_path, handle1)
    center2 = get_entity_center(dxf_path, handle2)

    if center1 is None or center2 is None:
        return []

    p1 = Vec2(center1[0], center1[1])
    p2 = Vec2(center2[0], center2[1])

    xmin = min(p1.x, p2.x) - max_distance_from_line
    xmax = max(p1.x, p2.x) + max_distance_from_line
    ymin = min(p1.y, p2.y) - max_distance_from_line
    ymax = max(p1.y, p2.y) + max_distance_from_line

    candidates = find_entities_in_region(
        dxf_path, xmin, ymin, xmax, ymax,
        layer_pattern=layer_pattern
    )

    results = []
    line_vec = p2 - p1
    line_length = line_vec.magnitude

    if line_length < 0.001:
        return []

    for entity_info in candidates:
        if entity_info['handle'] in (handle1, handle2):
            continue

        if 'center' not in entity_info:
            continue

        ec = Vec2(entity_info['center'][0], entity_info['center'][1])

        v = ec - p1
        cross = line_vec.x * v.y - line_vec.y * v.x
        perp_distance = abs(cross) / line_length

        if perp_distance <= max_distance_from_line:
            projection = v.dot(line_vec) / line_length

            if 0 <= projection <= line_length:
                entity_info['distance_from_centerline'] = float(perp_distance)
                entity_info['projection_along_line'] = float(projection)
                results.append(entity_info)

    results.sort(key=lambda x: x['distance_from_centerline'])
    return results


def find_adjacent_entities(
    dxf_path: str | Path,
    handle: str,
    max_distance: float = 200.0,
    layer_pattern: Optional[str] = None,
    entity_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Find entities adjacent to (near) a given entity.

    Args:
        dxf_path: Path to DXF file
        handle: Reference entity handle
        max_distance: Maximum distance to consider "adjacent"
        layer_pattern: Optional layer filter
        entity_type: Optional entity type filter

    Returns:
        List of entity info dicts with added 'distance' key, sorted by distance
    """
    center = get_entity_center(dxf_path, handle)
    if center is None:
        return []

    nearby = find_entities_near_point(
        dxf_path,
        center[0],
        center[1],
        max_distance,
        layer_pattern=layer_pattern,
        entity_type=entity_type,
    )

    results = [e for e in nearby if e['handle'] != handle]
    return results
