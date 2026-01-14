"""
Robot URDF management service.

This module manages robot URDF files and archives.
"""

import importlib.resources
import io
import logging
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import RobotManager

from leropilot.exceptions import ResourceNotFoundError

from .paths import get_robot_urdf_dir

logger = logging.getLogger(__name__)


class RobotUrdfManager:
    """Manager for robot URDF files and archives."""

    def __init__(self, robot_manager: "RobotManager | None" = None) -> None:
        """
        Initialize URDF manager.

        Args:
            robot_manager: Optional RobotManager instance. If not provided, will be
                         obtained via get_robot_manager() when needed.
        """
        self._robot_manager = robot_manager

    def _get_robot_manager(self) -> "RobotManager":
        """Get robot manager instance (lazy loading to avoid circular imports)."""
        if self._robot_manager is None:
            from .manager import get_robot_manager

            self._robot_manager = get_robot_manager()
        return self._robot_manager

    def _get_urdf_file(self, robot_id: str) -> Path:
        """Internal helper returning the expected custom URDF file path for a robot.

        Note: this returns the canonical path where a custom URDF would be stored;
        it does not guarantee the file exists. Callers should check existence.
        """
        return get_robot_urdf_dir(robot_id) / "robot.urdf"

    def delete_custom_urdf(self, robot_id: str) -> None:
        """Delete a previously uploaded custom URDF and any related resource files.

        Raises:
            ValueError: if the robot does not exist.
            FileNotFoundError: if no custom URDF is present on disk.
            RuntimeError: for other failures during deletion.
        """
        robot = self._get_robot_manager().get_robot(robot_id)
        if robot is None:
            raise ValueError("Robot not found")
        urdf_file = self._get_urdf_file(robot_id)
        if not urdf_file.exists():
            raise FileNotFoundError("Custom URDF not found")

        # Remove the entire urdf directory tree for this robot
        urdf_dir = urdf_file.parent

        try:
            shutil.rmtree(urdf_dir)
            # If robot dir is empty after removal, remove it as well
            robot_dir = urdf_dir.parent
            try:
                if robot_dir.exists() and not any(robot_dir.iterdir()):
                    robot_dir.rmdir()
            except Exception:
                # Ignore failures to remove parent dir
                pass
        except Exception as e:
            raise RuntimeError(f"Failed to delete URDF: {e}") from e

    def upload_custom_urdf(self, robot_id: str, data: bytes) -> Path:
        """Upload and validate a custom URDF file or archive.

        Args:
            robot_id: Robot ID
            data: URDF file content (raw .urdf, .zip, or .tar.gz)

        Returns:
            Path to the saved robot.urdf file

        Raises:
            ResourceNotFoundError: if robot doesn't exist
            ValueError: if validation fails or archive format is invalid
        """
        # Basic validation
        robot = self._get_robot_manager().get_robot(robot_id)
        if robot is None:
            raise ResourceNotFoundError("hardware.robot_device.not_found", id=robot_id)

        target_dir = get_robot_urdf_dir(robot_id, create=True)
        target_dir.mkdir(parents=True, exist_ok=True)

        def _validate_and_mark(urdf_file: Path) -> None:
            from leropilot.utils.urdf import validate_file

            result = validate_file(str(urdf_file))
            if not result.get("valid", False):
                raise ValueError({"error": "URDF validation failed", "details": result})

            # Validation passed; custom URDF file is present on disk (no flag required)

        if data.startswith(b"PK"):
            # ZIP archive
            return self._process_zip_archive(data, target_dir, _validate_and_mark)
        elif data[:2] == b"\x1f\x8b":
            # tar.gz archive
            return self._process_targz_archive(data, target_dir, _validate_and_mark)
        else:
            # Raw URDF file
            return self._process_raw_urdf(data, target_dir, _validate_and_mark)

    def _process_zip_archive(self, data: bytes, target_dir: Path, validate_fn: callable) -> Path:
        """Process ZIP archive containing URDF."""
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                top_urdfs = [
                    n
                    for n in names
                    if os.path.basename(n).lower().endswith(".urdf") and ("/" not in n and "\\" not in n)
                ]
                if len(top_urdfs) != 1:
                    raise ValueError("Archive must contain exactly one top-level .urdf file")
                with tempfile.TemporaryDirectory() as tmpd:
                    zf.extractall(tmpd)
                    for root, _dirs, files in os.walk(tmpd):
                        for f in files:
                            src = Path(root) / f
                            rel = src.relative_to(tmpd)
                            dest = target_dir / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)

                    top_urdf_name = top_urdfs[0]
                    src_urdf = target_dir / os.path.basename(top_urdf_name)
                    dest_urdf = target_dir / "robot.urdf"
                    if not src_urdf.exists():
                        raise ValueError(f"Expected URDF file not found: {src_urdf}")
                    if src_urdf.name != "robot.urdf":
                        src_urdf.rename(dest_urdf)

                    validate_fn(dest_urdf)
                    return dest_urdf
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to process ZIP archive: {e}") from e

    def _process_targz_archive(self, data: bytes, target_dir: Path, validate_fn: callable) -> Path:
        """Process tar.gz archive containing URDF."""
        try:
            with tempfile.TemporaryDirectory() as tmpd:
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                    members = [m for m in tf.getmembers() if m.isfile()]
                    top_urdfs = [
                        m.name
                        for m in members
                        if os.path.basename(m.name).lower().endswith(".urdf")
                        and ("/" not in m.name and "\\" not in m.name)
                    ]
                    if len(top_urdfs) != 1:
                        raise ValueError("Archive must contain exactly one top-level .urdf file")
                    tf.extractall(tmpd)
                    for root, _dirs, files in os.walk(tmpd):
                        for f in files:
                            src = Path(root) / f
                            rel = src.relative_to(tmpd)
                            dest = target_dir / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)

                    top_urdf_name = top_urdfs[0]
                    src_urdf = target_dir / os.path.basename(top_urdf_name)
                    dest_urdf = target_dir / "robot.urdf"
                    if not src_urdf.exists():
                        raise ValueError(f"Expected URDF file not found: {src_urdf}")
                    if src_urdf.name != "robot.urdf":
                        src_urdf.rename(dest_urdf)

                    validate_fn(dest_urdf)
                    return dest_urdf
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to process tar.gz archive: {e}") from e

    def _process_raw_urdf(self, data: bytes, target_dir: Path, validate_fn: callable) -> Path:
        """Process raw URDF file."""
        try:
            dest_urdf = target_dir / "robot.urdf"
            with open(dest_urdf, "wb") as fh:
                fh.write(data)
            validate_fn(dest_urdf)
            return dest_urdf
        except Exception as e:
            raise ValueError(f"Failed to save URDF: {e}") from e

    def get_robot_urdf_resource(self, robot_id: str, path: str = "robot.urdf") -> bytes | None:
        """Return the bytes content of a URDF file for a robot.

        Args:
            robot_id: persisted robot id
            path: resource path/filename to look up (defaults to "robot.urdf").

        Returns:
            `bytes` when a resource is found and read, or `None` when not found.

        Raises:
            ValueError: if the robot is not found.
        """
        from leropilot.utils.urdf import get_robot_resource

        robot = self._get_robot_manager().get_robot(robot_id)
        if robot is None:
            raise ValueError("Robot not found")

        # Check custom user-provided resources first
        urdf_dir = self._get_urdf_file(robot_id).parent
        user_file = urdf_dir / path
        if user_file.exists():
            try:
                return user_file.read_bytes()
            except Exception as e:
                raise RuntimeError(f"Failed to read custom URDF: {e}") from e

        # Resolve default via robot.definition.id (preferred over lerobot_name for resources)
        defn = robot.definition
        if isinstance(defn, str):
            raise ValueError("Robot.definition must be a RobotDefinition, not a string")
        # If there's no definition, there is no built-in URDF
        if not defn:
            return None

        # Use definition ID as the resource folder name
        resource = get_robot_resource(defn.id, path)

        if resource:
            # Use as_file to get a filesystem path to read from
            try:
                with importlib.resources.as_file(resource) as fp:
                    return fp.read_bytes()
            except Exception as e:
                raise RuntimeError(f"Failed to read packaged URDF: {e}") from e

        return None


# Singleton accessor for URDF manager
_robot_urdf_manager: RobotUrdfManager | None = None
_urdf_lock_import = __import__("threading").Lock()


def get_robot_urdf_manager() -> RobotUrdfManager:
    """Get the singleton RobotUrdfManager instance."""
    global _robot_urdf_manager
    with _urdf_lock_import:
        if _robot_urdf_manager is None:
            _robot_urdf_manager = RobotUrdfManager()
        return _robot_urdf_manager
