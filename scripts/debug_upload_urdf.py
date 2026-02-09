import io
import traceback
import zipfile

from leropilot.models.hardware import Robot
from leropilot.services.hardware.robots import get_robot_manager, get_robot_urdf_manager

manager = get_robot_manager()
manager._robots.pop("ZIP_URDF_DEV", None)
r = Robot(id="ZIP_URDF_DEV", name="ZIP_URDF_DEV", is_calibrated=False)
manager._robots["ZIP_URDF_DEV"] = r
bio = io.BytesIO()
with zipfile.ZipFile(bio, "w") as zf:
    zf.writestr("custom.urdf", b'<robot name="z">\n</robot>')
    zf.writestr("meshes/dummy.stl", b"solid dummy")

z = bio.getvalue()
try:
    path = get_robot_urdf_manager().upload_custom_urdf("ZIP_URDF_DEV", z)
    print("Saved path:", path)
except Exception:
    traceback.print_exc()
