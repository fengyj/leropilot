"""
URDF file validation and parsing service.

Handles:
- Parsing URDF files using urdf_parser_py
- Validating URDF structure and joint configuration
- Extracting joint and link information
- Checking motor count vs URDF joints
- Integration with LeRobot robot models

URDF is used by LeRobot to define robot kinematics and motor layout.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import URDF parser
try:
    from urdf_parser_py.urdf import URDF

    HAS_URDF_PARSER = True
except ImportError:
    HAS_URDF_PARSER = False
    logger.warning("urdf_parser_py not installed; URDF validation disabled")


class URDFJointInfo:
    """Information about a joint in URDF"""

    def __init__(
        self,
        name: str,
        joint_type: str,
        parent: str,
        child: str,
        origin_xyz: tuple[float, float, float],
        origin_rpy: tuple[float, float, float],
        axis: tuple[float, float, float],
        limits: dict | None = None,
    ) -> None:
        self.name = name
        self.joint_type = joint_type
        self.parent = parent
        self.child = child
        self.origin_xyz = origin_xyz
        self.origin_rpy = origin_rpy
        self.axis = axis
        self.limits = limits or {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.joint_type,
            "parent": self.parent,
            "child": self.child,
            "origin_xyz": self.origin_xyz,
            "origin_rpy": self.origin_rpy,
            "axis": self.axis,
            "limits": self.limits,
        }


class URDFLinkInfo:
    """Information about a link in URDF"""

    def __init__(self, name: str, mass: float | None = None, inertia: dict | None = None) -> None:
        self.name = name
        self.mass = mass
        self.inertia = inertia

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "mass": self.mass,
            "inertia": self.inertia,
        }


class URDFValidator:
    """Validates URDF files and extracts robot structure information"""

    def __init__(self) -> None:
        """Initialize URDF validator"""
        logger.info("URDFValidator initialized")
        if not HAS_URDF_PARSER:
            logger.warning("urdf_parser_py not installed; URDF validation will be limited")

    def validate_file(self, urdf_path: str) -> dict:
        """
        Validate URDF file and extract structure.

        Args:
            urdf_path: Path to URDF file

        Returns:
            Dict with validation results:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "joints": int,
                "links": int,
                "robot_name": str,
                "joint_info": List[URDFJointInfo],
                "link_info": List[URDFLinkInfo],
            }
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "joints": 0,
            "links": 0,
            "robot_name": None,
            "joint_info": [],
            "link_info": [],
        }

        if not HAS_URDF_PARSER:
            result["errors"].append("urdf_parser_py not installed")
            return result

        try:
            # Check file exists
            urdf_file = Path(urdf_path)
            if not urdf_file.exists():
                result["errors"].append(f"URDF file not found: {urdf_path}")
                return result

            # Parse URDF
            robot = URDF.from_xml_file(str(urdf_file))

            result["robot_name"] = robot.name
            result["joints"] = len(robot.joints)
            result["links"] = len(robot.links)

            # Extract joint information
            for joint in robot.joints:
                try:
                    origin_xyz = tuple(joint.origin.xyz) if joint.origin else (0, 0, 0)
                    origin_rpy = tuple(joint.origin.rpy) if joint.origin else (0, 0, 0)
                    axis = tuple(joint.axis) if joint.axis else (0, 0, 0)

                    limits = {}
                    if joint.limit:
                        limits = {
                            "lower": joint.limit.lower,
                            "upper": joint.limit.upper,
                            "effort": joint.limit.effort,
                            "velocity": joint.limit.velocity,
                        }

                    joint_info = URDFJointInfo(
                        name=joint.name,
                        joint_type=joint.joint_type,
                        parent=joint.parent,
                        child=joint.child,
                        origin_xyz=origin_xyz,
                        origin_rpy=origin_rpy,
                        axis=axis,
                        limits=limits,
                    )
                    result["joint_info"].append(joint_info)
                except Exception as e:
                    logger.warning(f"Error parsing joint {joint.name}: {e}")
                    result["warnings"].append(f"Error parsing joint {joint.name}: {e}")

            # Extract link information
            for link in robot.links:
                try:
                    mass = None
                    inertia = None

                    if link.inertial:
                        mass = link.inertial.mass
                        if link.inertial.inertia:
                            inertia = {
                                "ixx": link.inertial.inertia.ixx,
                                "iyy": link.inertial.inertia.iyy,
                                "izz": link.inertial.inertia.izz,
                                "ixy": link.inertial.inertia.ixy,
                                "ixz": link.inertial.inertia.ixz,
                                "iyz": link.inertial.inertia.iyz,
                            }

                    link_info = URDFLinkInfo(name=link.name, mass=mass, inertia=inertia)
                    result["link_info"].append(link_info)
                except Exception as e:
                    logger.warning(f"Error parsing link {link.name}: {e}")
                    result["warnings"].append(f"Error parsing link {link.name}: {e}")

            # Perform validation checks
            errors = self._validate_structure(robot)
            result["errors"].extend(errors)

            result["valid"] = len(result["errors"]) == 0
            logger.info(f"URDF validation: valid={result['valid']}, joints={result['joints']}, links={result['links']}")
            return result

        except Exception as e:
            logger.error(f"Error parsing URDF file: {e}")
            result["errors"].append(f"Failed to parse URDF: {str(e)}")
            return result

    def _validate_structure(self, robot: URDF) -> list[str]:
        """
        Perform validation checks on URDF structure.

        Returns:
            List of error messages
        """
        errors = []

        # Check for root link (typically "base_link")
        root_links = set(link.name for link in robot.links)
        all_child_links = set(j.child for j in robot.joints)
        orphan_links = root_links - all_child_links

        if not orphan_links:
            errors.append("No root link found (no links without parents)")
        elif len(orphan_links) > 1:
            errors.append(f"Multiple root links found: {orphan_links}")

        # Check for cycles in joint tree
        try:
            self._check_kinematic_chain(robot)
        except ValueError as e:
            errors.append(str(e))

        # Check for missing joint limits
        for joint in robot.joints:
            if joint.joint_type in ["revolute", "prismatic"]:
                if not joint.limit:
                    errors.append(f"Joint '{joint.name}' missing limits")

        return errors

    def _check_kinematic_chain(self, robot: URDF) -> None:
        """
        Check for cycles in kinematic chain.

        Raises:
            ValueError if cycle detected
        """
        # Build adjacency map
        children_map: dict[str, list[str]] = {}
        for joint in robot.joints:
            parent = joint.parent
            child = joint.child
            if parent not in children_map:
                children_map[parent] = []
            children_map[parent].append(child)

        # Find root
        all_links = set(link.name for link in robot.links)
        all_children = set(j.child for j in robot.joints)
        roots = all_links - all_children

        if len(roots) != 1:
            raise ValueError(f"Expected 1 root link, found {len(roots)}")

        # DFS to detect cycles
        visited = set()
        rec_stack = set()

        def dfs(link: str) -> None:
            visited.add(link)
            rec_stack.add(link)

            for child in children_map.get(link, []):
                if child not in visited:
                    dfs(child)
                elif child in rec_stack:
                    raise ValueError(f"Cycle detected: {link} -> {child}")

            rec_stack.remove(link)

        dfs(list(roots)[0])

    def get_joint_chain(self, urdf_path: str, from_link: str, to_link: str) -> list[str] | None:
        """
        Get kinematic chain between two links.

        Args:
            urdf_path: Path to URDF file
            from_link: Starting link name
            to_link: Ending link name

        Returns:
            List of joint names in chain, or None if no path exists
        """
        if not HAS_URDF_PARSER:
            logger.error("urdf_parser_py not installed")
            return None

        try:
            robot = URDF.from_xml_file(str(urdf_path))

            # Build adjacency map
            joint_map = {}
            for joint in robot.joints:
                joint_map[joint.parent] = (joint.name, joint.child)

            # Traverse from from_link to to_link
            chain = []
            current = from_link

            visited = set()
            while current != to_link and current not in visited:
                visited.add(current)
                if current not in joint_map:
                    logger.warning(f"No joint found for link {current}")
                    return None

                joint_name, next_link = joint_map[current]
                chain.append(joint_name)
                current = next_link

            if current == to_link:
                return chain
            else:
                logger.warning(f"No path found from {from_link} to {to_link}")
                return None
        except Exception as e:
            logger.error(f"Error getting joint chain: {e}")
            return None

    def validate_motor_count(
        self,
        urdf_path: str,
        motor_count: int,
        motor_ids: list[int] | None = None,
    ) -> tuple[bool, str]:
        """
        Validate that motor count matches URDF actuated joints.

        Args:
            urdf_path: Path to URDF file
            motor_count: Number of motors found
            motor_ids: Optional list of motor IDs for detailed checking

        Returns:
            Tuple of (is_valid, message)
        """
        if not HAS_URDF_PARSER:
            return True, "URDF validation skipped (urdf_parser_py not installed)"

        try:
            robot = URDF.from_xml_file(str(urdf_path))

            # Count actuated joints (not fixed/floating/planar)
            actuated_joints = [j for j in robot.joints if j.joint_type in ["revolute", "continuous", "prismatic"]]

            actuated_count = len(actuated_joints)

            if motor_count != actuated_count:
                return (
                    False,
                    f"Motor count mismatch: found {motor_count} motors but URDF has {actuated_count} actuated joints",
                )

            return True, f"Motor count matches URDF: {motor_count} motors, {actuated_count} actuated joints"
        except Exception as e:
            logger.error(f"Error validating motor count: {e}")
            return False, f"Error validating motor count: {str(e)}"
