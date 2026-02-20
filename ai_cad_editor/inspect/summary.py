from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import ezdxf
from ezdxf.entities import DXFEntity
from ezdxf.layouts import BaseLayout
from ezdxf.math import Vec2, Vec3
from ezdxf.bbox import extents as bbox_extents


# Helper functions

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if math.isfinite(v):
            return v
        return None
    except Exception:
        return None


def vec3_to_list(v: Any) -> Optional[List[float]]:
    try:
        vv = Vec3(v)
        return [float(vv.x), float(vv.y), float(vv.z)]
    except Exception:
        return None


def clean_text(s: str) -> str:
    # normalize whitespace, keep it human + search friendly
    s = s.replace("\x00", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def entity_handle(e: DXFEntity) -> Optional[str]:
    try:
        h = e.dxf.handle
        return str(h) if h else None
    except Exception:
        return None


def entity_layer(e: DXFEntity) -> Optional[str]:
    try:
        return e.dxf.layer
    except Exception:
        return None


def entity_color_raw(e: DXFEntity) -> Optional[int]:
    # ACI color number, may be 0/256 "BYBLOCK/BYLAYER"
    try:
        c = e.dxf.color
        return int(c) if c is not None else None
    except Exception:
        return None


def entity_linetype(e: DXFEntity) -> Optional[str]:
    try:
        return e.dxf.linetype
    except Exception:
        return None


def layout_name(layout: BaseLayout) -> str:
    try:
        return str(layout.name)
    except Exception:
        return "UNKNOWN"


def safe_bbox_for_entities(entities: Iterable[DXFEntity]) -> Optional[List[float]]:
    """
    Returns [xmin, ymin, xmax, ymax] from ezdxf's bbox extents when possible.
    Works for many entity types; skips those that break.
    """
    ents = []
    for e in entities:
        if not hasattr(e, "dxftype"):
            continue
        # Skip obviously troublesome / non-graphical
        if e.dxftype() in {"XRECORD", "DICTIONARY", "ACAD_PROXY_ENTITY"}:
            continue
        ents.append(e)
    if not ents:
        return None
    try:
        ex = bbox_extents(ents, fast=True)  # fast=True avoids some heavy curve sampling
        if ex is None:
            return None
        (xmin, ymin, zmin), (xmax, ymax, zmax) = ex.extmin, ex.extmax
        return [float(xmin), float(ymin), float(xmax), float(ymax)]
    except Exception:
        return None


def polyline_is_closed(e: DXFEntity) -> Optional[bool]:
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE":
            return bool(e.closed)
        if t == "POLYLINE":
            return bool(e.is_closed)
    except Exception:
        return None
    return None


def polyline_area_if_safe(e: DXFEntity) -> Optional[float]:
    """
    Computes area only for polylines we can confidently interpret as closed in XY.
    - LWPOLYLINE: supports bulges; ezdxf has get_area() for LWPolyline
    - POLYLINE: may be 2D/3D; we only accept 2D-ish planar cases and use vertices
    """
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE":
            if not e.closed:
                return None
            # ezdxf method accounts for bulge arcs
            a = e.get_area()
            return float(a) if math.isfinite(a) else None

        if t == "POLYLINE":
            if not e.is_closed:
                return None
            # Only accept 2D polyline (common in floorplans). For other cases, skip.
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

def lwpolyline_has_bulges(e: DXFEntity) -> bool:
    """True if LWPOLYLINE contains arc segments (bulge != 0)."""
    if e.dxftype() != "LWPOLYLINE":
        return False
    try:
        # get_points yields tuples like (x, y[, start_width, end_width, bulge])
        for p in e.get_points():
            # bulge is typically index 4 when present
            if len(p) >= 5 and abs(float(p[4])) > 1e-12:
                return True
    except Exception:
        return True
    return False


def polyline_vertices_xy_if_safe(e: DXFEntity) -> Optional[List[Vec2]]:
    """
    Return a list of XY vertices for closed polylines when we can safely treat them as straight segments.
    Returns None if unsafe/unsupported.
    """
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE":
            if not getattr(e, "closed", False):
                return None
            # If there are bulges, centroid/perimeter via straight segments is wrong.
            if lwpolyline_has_bulges(e):
                return None
            pts = [Vec2(p[0], p[1]) for p in e.get_points("xy")]
            return pts if len(pts) >= 3 else None

        if t == "POLYLINE":
            if not getattr(e, "is_closed", False):
                return None
            # Only accept typical 2D polylines.
            if getattr(e, "is_2d_polyline", False) is False and getattr(e, "is_polygon_mesh", False):
                return None
            pts = [Vec2(v.dxf.location.x, v.dxf.location.y) for v in e.vertices()]
            return pts if len(pts) >= 3 else None
    except Exception:
        return None
    return None


def polygon_perimeter(pts: List[Vec2]) -> float:
    per = 0.0
    n = len(pts)
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        per += (b - a).magnitude
    return float(per)


def polygon_centroid_xy(pts: List[Vec2]) -> Optional[List[float]]:
    """
    Centroid of a simple polygon (shoelace-based).
    Returns None if area is ~0.
    """
    n = len(pts)
    a2 = 0.0  # 2*area signed
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x1, y1 = pts[i].x, pts[i].y
        x2, y2 = pts[(i + 1) % n].x, pts[(i + 1) % n].y
        cross = x1 * y2 - x2 * y1
        a2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross

    if abs(a2) < 1e-12:
        return None
    cx /= (3.0 * a2)
    cy /= (3.0 * a2)
    return [float(cx), float(cy)]


def hatch_area_if_safe(e: DXFEntity) -> Optional[float]:
    # HATCH area can be tricky if boundaries are complex; ezdxf supports area() for some
    if e.dxftype() != "HATCH":
        return None
    try:
        # Some ezdxf versions expose .area property; others have methods.
        a = getattr(e, "area", None)
        if a is None:
            # fallback: boundary paths may be present but computing area robustly is non-trivial
            return None
        a = float(a)
        return a if math.isfinite(a) else None
    except Exception:
        return None


def extract_text_entity(e: DXFEntity) -> Optional[Dict[str, Any]]:
    t = e.dxftype()
    try:
        if t == "TEXT":
            raw = e.dxf.text or ""
            content = clean_text(raw)
            if not content:
                return None
            ins = vec3_to_list(e.dxf.insert)
            return {
                "handle": entity_handle(e),
                "dxftype": "TEXT",
                "layer": entity_layer(e),
                "color": entity_color_raw(e),
                "linetype": entity_linetype(e),
                "text": content,
                "insert": ins,
                "height": safe_float(getattr(e.dxf, "height", None)),
                "rotation": safe_float(getattr(e.dxf, "rotation", None)),
            }

        if t == "MTEXT":
            # plain_text() is what you usually want for searching/room-name matching
            content = clean_text(e.plain_text())
            if not content:
                return None
            ins = vec3_to_list(e.dxf.insert)
            return {
                "handle": entity_handle(e),
                "dxftype": "MTEXT",
                "layer": entity_layer(e),
                "color": entity_color_raw(e),
                "linetype": entity_linetype(e),
                "text": content,
                "insert": ins,
                "char_height": safe_float(getattr(e.dxf, "char_height", None)),
                "rotation": safe_float(getattr(e.dxf, "rotation", None)),
            }
    except Exception:
        return None
    return None


# Main summary functions

def summarize_dxf(
    dxf_path: str | Path,
    *,
    include_paperspace: bool = False,
    max_text_items: int = 5000,
    max_boundary_candidates: int = 5000,
) -> Dict[str, Any]:
    """
    Parse a DXF file and return a structured summary.

    Extracts layers, entity counts, text content, and boundary candidates (closed polylines).
    Designed for robust parsing - failures in individual entities are contained.
    """
    p = Path(dxf_path)
    doc = ezdxf.readfile(p)

    # metadata / units
    try:
        units = int(doc.header.get("$INSUNITS", 0) or 0)
    except Exception:
        units = None

    try:
        acadver = str(doc.dxfversion)
    except Exception:
        acadver = None

    layouts: List[BaseLayout] = [doc.modelspace()]
    if include_paperspace:
        try:
            for name in doc.layout_names():
                if name.lower() == "model":
                    continue
                layouts.append(doc.layouts.get(name))
        except Exception:
            pass

    # collect entities for bbox/extents
    all_entities: List[DXFEntity] = []
    for layout in layouts:
        try:
            for e in layout:
                all_entities.append(e)
        except Exception:
            continue

    drawing_bbox = safe_bbox_for_entities(all_entities)

    # layers inventory
    layer_table: Dict[str, Any] = {}
    try:
        for layer in doc.layers:
            name = str(layer.dxf.name)
            layer_table[name] = {
                "name": name,
                "color": safe_float(getattr(layer.dxf, "color", None)),
                "true_color": getattr(layer.dxf, "true_color", None),
                "linetype": getattr(layer.dxf, "linetype", None),
                "lineweight": getattr(layer.dxf, "lineweight", None),
                "plot": bool(getattr(layer.dxf, "plot", 1)),
                "is_off": bool(layer.is_off()),
                "is_frozen": bool(layer.is_frozen()),
                "is_locked": bool(layer.is_locked()),
            }
    except Exception:
        layer_table = {}

    # entity counts by layer and type
    entity_counts_by_type: Dict[str, int] = {}
    entity_counts_by_layer: Dict[str, Dict[str, int]] = {}

    def bump(d: Dict[str, int], k: str, inc: int = 1) -> None:
        d[k] = int(d.get(k, 0)) + inc

    # blocks / inserts
    block_defs: List[Dict[str, Any]] = []
    inserts_by_block: Dict[str, int] = {}

    try:
        for blk in doc.blocks:
            # Skip special blocks like *Model_Space, *Paper_Space, etc.
            name = str(blk.name)
            if name.startswith("*"):
                continue
            block_defs.append({
                "name": name,
                "entity_count": sum(1 for _ in blk),
            })
    except Exception:
        block_defs = []

    # text index
    text_items: List[Dict[str, Any]] = []

    # boundary candidates
    boundary_candidates: List[Dict[str, Any]] = []

    for layout in layouts:
        lname = layout_name(layout)
        try:
            for e in layout:
                try:
                    t = e.dxftype()
                except Exception:
                    continue

                bump(entity_counts_by_type, t)

                layer = entity_layer(e) or "UNKNOWN"
                if layer not in entity_counts_by_layer:
                    entity_counts_by_layer[layer] = {}
                bump(entity_counts_by_layer[layer], t)

                # INSERT stats
                if t == "INSERT":
                    try:
                        bname = str(e.dxf.name)
                        inserts_by_block[bname] = int(inserts_by_block.get(bname, 0)) + 1
                    except Exception:
                        pass

                # text index
                if t in {"TEXT", "MTEXT"} and len(text_items) < max_text_items:
                    item = extract_text_entity(e)
                    if item:
                        item["layout"] = lname
                        text_items.append(item)

                # boundary candidates (future "rooms")
                if len(boundary_candidates) < max_boundary_candidates:
                    if t in {"LWPOLYLINE", "POLYLINE"}:
                        closed = polyline_is_closed(e)
                        if closed:
                            pts = polyline_vertices_xy_if_safe(e)
                            boundary_candidates.append({
                                "handle": entity_handle(e),
                                "dxftype": t,
                                "layout": lname,
                                "layer": layer,
                                "color": entity_color_raw(e),
                                "linetype": entity_linetype(e),
                                "is_closed": True,
                                "vertex_count": (len(pts) if pts else None),
                                "area": polyline_area_if_safe(e),
                                "perimeter": (polygon_perimeter(pts) if pts else None),
                                "centroid_xy": (polygon_centroid_xy(pts) if pts else None),
                                "bbox": safe_bbox_for_entities([e]),
                            })

                    elif t == "HATCH":
                        boundary_candidates.append({
                            "handle": entity_handle(e),
                            "dxftype": "HATCH",
                            "layout": lname,
                            "layer": layer,
                            "color": entity_color_raw(e),
                            "linetype": entity_linetype(e),
                            "area": hatch_area_if_safe(e),
                            "bbox": safe_bbox_for_entities([e]),
                        })

        except Exception:
            continue

    # layer list with counts
    layers_out: List[Dict[str, Any]] = []
    for lname, counts in sorted(entity_counts_by_layer.items(), key=lambda x: x[0].lower()):
        props = layer_table.get(lname, {"name": lname})
        layers_out.append({
            **props,
            "entity_counts": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))),
            "total_entities": int(sum(counts.values())),
        })

    # blocks with insert counts
    block_defs_map = {b["name"]: b for b in block_defs}
    blocks_out: List[Dict[str, Any]] = []
    for bname in sorted(set(list(block_defs_map.keys()) + list(inserts_by_block.keys())), key=str.lower):
        blocks_out.append({
            "name": bname,
            "definition_entity_count": block_defs_map.get(bname, {}).get("entity_count"),
            "insert_count": int(inserts_by_block.get(bname, 0)),
        })

    summary: Dict[str, Any] = {
        "meta": {
            "source_file": str(p),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "dxf_version": acadver,
            "insunits_header_code": units,
            "include_paperspace": bool(include_paperspace),
        },
        "drawing": {
            "bbox_xy": drawing_bbox,  # [xmin, ymin, xmax, ymax]
            "layout_names": [layout_name(l) for l in layouts],
            "entity_counts_by_type": dict(sorted(entity_counts_by_type.items(), key=lambda kv: (-kv[1], kv[0]))),
            "total_entities": int(sum(entity_counts_by_type.values())),
        },
        "layers": layers_out,
        "blocks": blocks_out,
        "text_index": {
            "count": int(len(text_items)),
            "truncated": bool(len(text_items) >= max_text_items),
            "items": text_items,
        },
        "boundary_candidates": {
            "count": int(len(boundary_candidates)),
            "truncated": bool(len(boundary_candidates) >= max_boundary_candidates),
            "items": boundary_candidates,
        },
        "notes": [
            "Areas are computed only for closed polylines and supported HATCH entities.",
            "This is a read-only summary - no modifications are performed.",
        ],
    }
    return summary


def write_summary_json(
    dxf_path: str | Path,
    out_path: str | Path,
    *,
    include_paperspace: bool = False,
) -> Path:
    summary = summarize_dxf(dxf_path, include_paperspace=include_paperspace)
    outp = Path(out_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return outp
