"""
Lightweight URDF parser and validator tailored for project's validation needs.

Provides:
- validate_file(urdf_path: str) -> dict
- get_joint_chain(urdf_path: str, from_link: str, to_link: str) -> list[str] | None
- validate_motor_count(urdf_path: str, motor_count: int) -> tuple[bool,str]

This implementation is intentionally small and focuses on the checks we need
(rather than providing a full URDF runtime parser). It uses the standard
xml.etree.ElementTree module to avoid external dependencies.

License: project-original (this file implemented in-project)
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


def _add_error(result: dict, code: str, message: str, location: str | None = None) -> None:
    entry = {"code": code, "message": message, "location": location}
    result.setdefault("error_details", []).append(entry)
    if location:
        result.setdefault("errors", []).append(f"{code} @ {location}: {message}")
    else:
        result.setdefault("errors", []).append(f"{code}: {message}")


def _add_warning(result: dict, code: str, message: str, location: str | None = None) -> None:
    entry = {"code": code, "message": message, "location": location}
    result.setdefault("warning_details", []).append(entry)
    if location:
        result.setdefault("warnings", []).append(f"{code} @ {location}: {message}")
    else:
        result.setdefault("warnings", []).append(f"{code}: {message}")


def _is_finite_number(v: object) -> bool:
    try:
        from math import isfinite

        return isinstance(v, (int, float)) and isfinite(v)
    except Exception:
        return False


def _parse_float_tuple(s: str | None, expected: int = 3) -> tuple[float, ...]:
    if not s:
        return tuple(0.0 for _ in range(expected))
    parts = s.strip().split()
    vals = []
    for p in parts:
        try:
            vals.append(float(p))
        except Exception:
            vals.append(0.0)
    # pad or trim
    if len(vals) < expected:
        vals += [0.0] * (expected - len(vals))
    return tuple(vals[:expected])


def validate_file(urdf_path: str) -> dict:
    """Validate URDF file and return structured result similar to previous validator."""
    result = {
        "valid": False,
        "errors": [],
        "error_details": [],
        "warnings": [],
        "warning_details": [],
        "joints": 0,
        "links": 0,
        "robot_name": None,
        "joint_info": [],
        "link_info": [],
    }

    try:
        p = Path(urdf_path)
        if not p.exists():
            _add_error(result, "URDF_NOT_FOUND", f"URDF file not found: {urdf_path}")
            return result

        tree = ET.parse(str(p))
        root = tree.getroot()

        if root.tag != "robot":
            _add_error(result, "URDF_INVALID_ROOT", f"Root tag is not <robot>: found <{root.tag}>")
            return result

        robot_name = root.attrib.get("name")
        result["robot_name"] = robot_name

        # Parse links
        links = []
        for ln in root.findall("link"):
            name = ln.attrib.get("name")
            mass = None
            inertia = None
            inertial = ln.find("inertial")
            if inertial is not None:
                mass_el = inertial.find("mass")
                if mass_el is not None and "value" in mass_el.attrib:
                    try:
                        mass = float(mass_el.attrib.get("value"))
                    except Exception:
                        mass = None
                inertia_el = inertial.find("inertia")
                if inertia_el is not None:
                    try:
                        inertia = {
                            k: float(inertia_el.attrib.get(k))
                            for k in ["ixx", "iyy", "izz", "ixy", "ixz", "iyz"]
                            if inertia_el.attrib.get(k) is not None
                        }
                    except Exception:
                        inertia = None
            links.append({"name": name, "mass": mass, "inertia": inertia})
            result["link_info"].append({"name": name, "mass": mass, "inertia": inertia})

        # Parse joints
        joints = []
        for jn in root.findall("joint"):
            name = jn.attrib.get("name")
            jtype = jn.attrib.get("type", "")
            parent_el = jn.find("parent")
            child_el = jn.find("child")
            parent = parent_el.attrib.get("link") if parent_el is not None else None
            child = child_el.attrib.get("link") if child_el is not None else None
            origin_el = jn.find("origin")
            origin_xyz = _parse_float_tuple(origin_el.attrib.get("xyz") if origin_el is not None else None)
            origin_rpy = _parse_float_tuple(origin_el.attrib.get("rpy") if origin_el is not None else None)
            axis_el = jn.find("axis")
            axis = _parse_float_tuple(axis_el.attrib.get("xyz") if axis_el is not None else None)
            limit_el = jn.find("limit")
            limits = None
            if limit_el is not None:
                try:
                    lower = (
                        float(limit_el.attrib.get("lower"))
                        if limit_el.attrib.get("lower") is not None
                        else None
                    )
                    upper = (
                        float(limit_el.attrib.get("upper"))
                        if limit_el.attrib.get("upper") is not None
                        else None
                    )
                    effort = (
                        float(limit_el.attrib.get("effort"))
                        if limit_el.attrib.get("effort") is not None
                        else None
                    )
                    velocity = (
                        float(limit_el.attrib.get("velocity"))
                        if limit_el.attrib.get("velocity") is not None
                        else None
                    )
                    limits = {
                        "lower": lower,
                        "upper": upper,
                        "effort": effort,
                        "velocity": velocity,
                    }
                except Exception:
                    limits = None

            joints.append(
                {
                    "name": name,
                    "type": jtype,
                    "parent": parent,
                    "child": child,
                    "origin_xyz": origin_xyz,
                    "origin_rpy": origin_rpy,
                    "axis": axis,
                    "limits": limits,
                }
            )
            result["joint_info"].append(
                {
                    "name": name,
                    "type": jtype,
                    "parent": parent,
                    "child": child,
                    "origin_xyz": origin_xyz,
                    "origin_rpy": origin_rpy,
                    "axis": axis,
                    "limits": limits,
                }
            )

        result["links"] = len(links)
        result["joints"] = len(joints)

        # Run semantic checks
        _validate_structure(parsed_joints=joints, parsed_links=links, result=result)

        result["valid"] = len(result["errors"]) == 0
        logger.info(f"URDF validation: valid={result['valid']}, joints={result['joints']}, links={result['links']}")
        return result

    except ET.ParseError as e:
        logger.error(f"Error parsing URDF XML: {e}")
        _add_error(result, "URDF_PARSE_ERROR", str(e))
        return result
    except Exception as e:
        logger.exception(f"Unexpected error validating URDF: {e}")
        _add_error(result, "URDF_UNKNOWN_ERROR", str(e))
        return result


def _validate_structure(parsed_joints: list[dict], parsed_links: list[dict], result: dict) -> None:
    # Duplicate names
    joint_names = [j.get("name") for j in parsed_joints]
    dup_joints = {n for n in joint_names if joint_names.count(n) > 1 and n is not None}
    if dup_joints:
        _add_error(result, "URDF_DUPLICATE_JOINT_NAME", f"Duplicate joint names: {sorted(dup_joints)}")

    link_names = [link.get("name") for link in parsed_links]
    dup_links = {n for n in link_names if link_names.count(n) > 1 and n is not None}
    if dup_links:
        _add_error(result, "URDF_DUPLICATE_LINK_NAME", f"Duplicate link names: {sorted(dup_links)}")

    # Root link checks
    root_links = set([link.get("name") for link in parsed_links if link.get("name") is not None])
    child_links = set([j.get("child") for j in parsed_joints if j.get("child") is not None])
    orphan_links = root_links - child_links
    if not orphan_links:
        _add_error(result, "URDF_NO_ROOT", "No root link found (no links without parents)")
    elif len(orphan_links) > 1:
        _add_error(result, "URDF_MULTIPLE_ROOTS", f"Multiple root links found: {sorted(orphan_links)}")

    # Cycle check via adjacency
    try:
        _check_kinematic_chain(parsed_joints, parsed_links)
    except ValueError as e:
        _add_error(result, "URDF_CYCLE", str(e))

    # Joint axis and limits checks
    for joint in parsed_joints:
        axis = joint.get("axis", (0.0, 0.0, 0.0))
        if all(abs(x) < 1e-9 for x in axis):
            _add_warning(result, "URDF_AXIS_ZERO", "Joint axis is zero vector", location=joint.get("name"))

        if joint.get("type") in ["revolute", "prismatic", "continuous"]:
            if not joint.get("limits"):
                if joint.get("type") != "continuous":
                    _add_error(
                        result,
                        "URDF_MISSING_LIMIT",
                        "Actuated joint missing limits",
                        location=joint.get("name"),
                    )
            else:
                lower = joint["limits"].get("lower")
                upper = joint["limits"].get("upper")
                if lower is None or upper is None or not (_is_finite_number(lower) and _is_finite_number(upper)):
                    _add_error(
                        result,
                        "URDF_LIMIT_INVALID",
                        "Joint limits are not finite numbers",
                        location=joint.get("name"),
                    )
                else:
                    if lower >= upper:
                        _add_error(
                            result,
                            "URDF_LIMIT_ORDER",
                            "Joint limit lower >= upper",
                            location=joint.get("name"),
                        )
                    if (upper - lower) > 1e6:
                        _add_warning(
                            result,
                            "URDF_LIMIT_SUSPICIOUS",
                            "Joint limit range suspiciously large",
                            location=joint.get("name"),
                        )

    # Link inertial checks
    for link in parsed_links:
        inertia = link.get("inertia")
        if not inertia:
            _add_warning(
                result,
                "URDF_MISSING_INERTIAL",
                "Link missing inertial information",
                location=link.get("name"),
            )
        else:
            for comp in ("ixx", "iyy", "izz"):
                val = inertia.get(comp)
                if val is None or not _is_finite_number(val) or val <= 0:
                    _add_error(
                        result,
                        "URDF_INVALID_INERTIA",
                        f"Invalid inertia component {comp}",
                        location=link.get("name"),
                    )


def _check_kinematic_chain(parsed_joints: list[dict], parsed_links: list[dict]) -> None:
    # adjacency map
    children_map: dict[str, list[str]] = {}
    for j in parsed_joints:
        parent = j.get("parent")
        child = j.get("child")
        if not parent or not child:
            continue
        children_map.setdefault(parent, []).append(child)

    all_links = set(link.get("name") for link in parsed_links if link.get("name") is not None)
    all_children = set(j.get("child") for j in parsed_joints if j.get("child") is not None)
    roots = all_links - all_children
    if len(roots) != 1:
        raise ValueError(f"Expected 1 root link, found {len(roots)}")

    root = list(roots)[0]

    visited = set()
    stack = set()

    def dfs(link: str) -> None:
        visited.add(link)
        stack.add(link)
        for c in children_map.get(link, []):
            if c not in visited:
                dfs(c)
            elif c in stack:
                raise ValueError(f"Cycle detected: {link} -> {c}")
        stack.remove(link)

    dfs(root)


def get_joint_chain(urdf_path: str, from_link: str, to_link: str) -> list[str] | None:
    try:
        # Reuse simple parser
        parsed = validate_file(urdf_path)
        if parsed.get("errors"):
            return None

        # Build parent->(joint_name, child)
        joint_map = {}
        for j in parsed.get("joint_info", []):
            parent = j.get("parent")
            joint_map.setdefault(parent, []).append((j.get("name"), j.get("child")))

        # BFS/DFS
        from collections import deque

        q = deque([(from_link, [])])
        seen = set()
        while q:
            cur, path = q.popleft()
            if cur == to_link:
                return path
            if cur in seen:
                continue
            seen.add(cur)
            for joint in joint_map.get(cur, []):
                q.append((joint[1], path + [joint[0]]))
        return None
    except Exception as e:
        logger.error(f"Error getting joint chain: {e}")
        return None


def validate_motor_count(urdf_path: str, motor_count: int, motor_ids: list[int] | None = None) -> tuple[bool, str]:
    parsed = validate_file(urdf_path)
    if parsed.get("errors"):
        return False, "URDF validation failed"

    actuated = [j for j in parsed.get("joint_info", []) if j.get("type") in ["revolute", "continuous", "prismatic"]]
    actuated_count = len(actuated)

    if motor_count != actuated_count:
        return False, f"Motor count mismatch: found {motor_count} motors but URDF has {actuated_count} actuated joints"
    return True, f"Motor count matches URDF: {motor_count} motors, {actuated_count} actuated joints"
