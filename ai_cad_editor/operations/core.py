from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import ezdxf
from ezdxf.entities import DXFEntity
from ezdxf.math import Vec2


def _safe_float(x: Any) -> Optional[float]:
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
    try:
        h = e.dxf.handle
        return str(h) if h else None
    except Exception:
        return None


def _entity_layer(e: DXFEntity) -> Optional[str]:
    try:
        return e.dxf.layer
    except Exception:
        return None


def _entity_color_raw(e: DXFEntity) -> Optional[int]:
    try:
        c = e.dxf.color
        return int(c) if c is not None else None
    except Exception:
        return None


def _entity_linetype(e: DXFEntity) -> Optional[str]:
    try:
        return e.dxf.linetype
    except Exception:
        return None


def _polyline_area_if_safe(e: DXFEntity) -> Optional[float]:
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE":
            if not e.closed:
                return None
            if hasattr(e, 'get_area') and callable(e.get_area):
                a = e.get_area()
                return float(a) if math.isfinite(a) else None
            if hasattr(e, 'get_points'):
                points = list(e.get_points('xy'))
                if len(points) < 3:
                    return None
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
            if getattr(e, "is_2d_polyline", False) is False and getattr(e, "is_polygon_mesh", False):
                return None
            pts2: List[Vec2] = []
            for v in e.vertices():
                p = v.dxf.location
                pts2.append(Vec2(p.x, p.y))
            if len(pts2) < 3:
                return None
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


def list_layers(dxf_path: str | Path) -> List[Dict[str, Any]]:
    doc = ezdxf.readfile(Path(dxf_path))

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
    doc = ezdxf.readfile(Path(dxf_path))

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
    doc = ezdxf.readfile(Path(dxf_path))

    try:
        entity = doc.entitydb[handle]
    except KeyError:
        return None

    etype = entity.dxftype()

    if etype in ("LWPOLYLINE", "POLYLINE"):
        return _polyline_area_if_safe(entity)

    if etype == "HATCH":
        return _hatch_area_if_safe(entity)

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
    doc = ezdxf.readfile(Path(dxf_path))

    if layer_name in doc.layers:
        layer = doc.layers.get(layer_name)
        layer.dxf.color = color

    for entity in doc.modelspace().query(f'*[layer=="{layer_name}"]'):
        try:
            entity.dxf.color = color
        except Exception:
            continue

    out = Path(output_path) if output_path else Path(dxf_path)
    doc.saveas(out)
    return out


def delete_entity(
    dxf_path: str | Path,
    handle: str,
    output_path: Optional[str | Path] = None,
) -> Path:
    doc = ezdxf.readfile(Path(dxf_path))

    try:
        entity = doc.entitydb[handle]
        entity.destroy()
    except KeyError:
        raise KeyError(f"Entity with handle '{handle}' not found")

    out = Path(output_path) if output_path else Path(dxf_path)
    doc.saveas(out)
    return out


def edit_text(
    dxf_path: str | Path,
    handle: str,
    new_text: str,
    output_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
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

    out = Path(output_path) if output_path else Path(dxf_path)
    doc.saveas(out)

    return {
        "success": True,
        "handle": handle,
        "old_text": old_text,
        "new_text": new_text,
        "output_path": str(out),
    }
