from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import ezdxf


def _snap_coord(val: float, tolerance: float) -> float:
    if tolerance <= 0:
        return val
    return round(val / tolerance) * tolerance


def _snap_point(x: float, y: float, tolerance: float) -> Tuple[float, float]:
    return (_snap_coord(x, tolerance), _snap_coord(y, tolerance))


def _build_planar_graph(
    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]],
) -> Dict[Tuple[float, float], List[Tuple[Tuple[float, float], float]]]:
    adj: Dict = defaultdict(list)
    for (a, b) in segments:
        if a == b:
            continue
        angle_ab = math.atan2(b[1] - a[1], b[0] - a[0])
        angle_ba = math.atan2(a[1] - b[1], a[0] - b[0])
        adj[a].append((b, angle_ab))
        adj[b].append((a, angle_ba))

    for node in adj:
        adj[node].sort(key=lambda item: item[1])

    return dict(adj)


def _next_halfedge(
    u: Tuple[float, float],
    v: Tuple[float, float],
    adj: Dict,
) -> Optional[Tuple[float, float]]:
    if v not in adj:
        return None

    neighbors = adj[v]
    if not neighbors:
        return None

    reverse_angle = math.atan2(u[1] - v[1], u[0] - v[0])

    best_w: Optional[Tuple[float, float]] = None
    best_delta = float("inf")

    for (w, angle) in neighbors:
        delta = (angle - reverse_angle) % (2 * math.pi)
        if delta < 1e-10:
            delta += 2 * math.pi
        if delta < best_delta:
            best_delta = delta
            best_w = w

    return best_w


def _trace_face(
    start_u: Tuple[float, float],
    start_v: Tuple[float, float],
    adj: Dict,
    max_iter: int = 2000,
) -> Optional[List[Tuple[float, float]]]:
    polygon: List[Tuple[float, float]] = []
    u, v = start_u, start_v

    for _ in range(max_iter):
        polygon.append(u)
        w = _next_halfedge(u, v, adj)
        if w is None:
            return None
        u, v = v, w
        if u == start_u and v == start_v:
            break
    else:
        return None

    return polygon if len(polygon) >= 3 else None


def _shoelace_area(polygon: List[Tuple[float, float]]) -> float:
    n = len(polygon)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    return abs(area) / 2.0


def _point_in_polygon(
    px: float, py: float, polygon: List[Tuple[float, float]]
) -> bool:
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > py) != (yj > py):
            if px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def _point_left_of_line(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> bool:
    return (bx - ax) * (py - ay) - (by - ay) * (px - ax) > 0


def reconstruct_room_area(
    dxf_path: str,
    x: float,
    y: float,
    layer_pattern: str = None,
    tolerance: float = 10.0,
) -> Dict[str, Any]:
    try:
        doc = ezdxf.readfile(Path(dxf_path))
    except Exception as e:
        return {"error": f"Failed to read DXF: {e}"}

    msp = doc.modelspace()

    try:
        if layer_pattern:
            entities = list(msp.query(f'LINE[layer=="{layer_pattern}"]'))
        else:
            entities = list(msp.query("LINE"))
    except Exception as e:
        return {"error": f"Entity query failed: {e}"}

    if not entities:
        hint = f" on layer '{layer_pattern}'" if layer_pattern else ""
        return {"error": f"No LINE entities found{hint}"}

    seen: set = set()
    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

    for e in entities:
        try:
            a = _snap_point(e.dxf.start.x, e.dxf.start.y, tolerance)
            b = _snap_point(e.dxf.end.x, e.dxf.end.y, tolerance)
            if a == b:
                continue
            key = (min(a, b), max(a, b))
            if key not in seen:
                seen.add(key)
                segments.append((a, b))
        except Exception:
            continue

    if not segments:
        return {"error": "No valid LINE segments after snapping. Try a larger tolerance."}

    adj = _build_planar_graph(segments)

    sx, sy = _snap_point(x, y, tolerance)

    best_seg: Optional[Tuple] = None
    best_dist = float("inf")

    for (a, b) in segments:
        dx_ab = b[0] - a[0]
        dy_ab = b[1] - a[1]
        len_sq = dx_ab * dx_ab + dy_ab * dy_ab
        if len_sq < 1e-20:
            continue
        t = max(0.0, min(1.0, ((sx - a[0]) * dx_ab + (sy - a[1]) * dy_ab) / len_sq))
        px = a[0] + t * dx_ab
        py = a[1] + t * dy_ab
        dist = math.sqrt((sx - px) ** 2 + (sy - py) ** 2)
        if dist < best_dist:
            best_dist = dist
            best_seg = (a, b)

    if best_seg is None:
        return {"error": "Could not find a segment near the seed point"}

    a, b = best_seg

    if _point_left_of_line(sx, sy, a[0], a[1], b[0], b[1]):
        start_u, start_v = a, b
    else:
        start_u, start_v = b, a

    polygon = _trace_face(start_u, start_v, adj)

    if polygon is None or len(polygon) < 3:
        polygon = _trace_face(start_v, start_u, adj)

    if polygon is None or len(polygon) < 3:
        return {
            "error": (
                "Could not reconstruct a closed room boundary. "
                "Try a larger tolerance (e.g. 50 or 100) or check the wall layer name."
            ),
            "segment_count": len(segments),
            "nearest_wall_distance": round(best_dist, 2),
        }

    area = _shoelace_area(polygon)
    inside = _point_in_polygon(sx, sy, polygon)

    return {
        "area": round(area, 2),
        "vertex_count": len(polygon),
        "polygon": [[round(v[0], 2), round(v[1], 2)] for v in polygon[:20]],
        "polygon_truncated": len(polygon) > 20,
        "segment_count": len(segments),
        "seed_inside_polygon": inside,
    }
