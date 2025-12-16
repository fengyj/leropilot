# Hardware Management Specification

## 1. Overview
This feature aims to provide a unified interface for managing hardware devices connected to the system, specifically robotic arms and cameras (including depth cameras). It allows users to identify, label, configure, and control these devices.

## 2. Functional Requirements

### 2.1 Device Identification & Management
- **Scan & List**: Automatically detect connected USB/Serial devices.
- **Unique Identification**: **Strict Requirement**. Devices *must* have a readable unique serial number to be supported. Devices without a unique ID cannot be added to the system.
- **Renaming**: Allow users to assign a human-readable "friendly name" to any device (e.g., "Left Arm", "Overhead Camera").
- **Tagging & Labels**: Adopt a **Key-Value Label** system (inspired by Kubernetes) for flexible management.
    - **Format**: `key: value` (e.g., `role: leader`, `position: left`).
    - **Label Selectors**: The system can query devices using selectors.
    - **Use Case Example**: "Start Recording" workflow automatically finds the device where `role=leader` to record controls from, and `role=follower` to send commands to.
- **Persistence**: Save metadata (name, labels, calibration) to local storage so it persists across reboots.

### 2.2 Label Strategy (Standard Labels)
Start with a set of recommended/standard labels to unify automation:
- `leropilot.io/role`: `leader` (teleop master), `follower` (teleop puppet), `standalone`.
- `leropilot.io/position`: `left`, `right`, `center`.
- `leropilot.io/type`: `arm`, `camera`, `gripper`.
- *Users can still add custom labels (e.g., `project: assembly-line-1`).*

### 2.2 Robotic Arms
- **Status Display**: Show connection status, current joint angles/coordinates.
- **Control Interface**:
    - **Joint Space**: Sliders/inputs for each joint angle.
    - **Cartesian Space (Inverse Kinematics)**: Inputs for specific Target Pose (X, Y, Z, Roll, Pitch, Yaw).
    - **Interactive Control**: 3D visualizer where the user can **drag** the end-effector using a Transform Gizmo (mouse interaction).
    - Speed/Acceleration settings.
    - Torque enable/disable.
- **URDF Management**:
    - Support built-in URDFs (from `lerobot`).
    - **Custom Upload**: Allow users to upload a custom URDF file for a specific device. This file overrides the default model for visualization and control.
- **Calibration**:
    - Guided calibration wizard.
    - Save calibration data linked to the specific hardware ID.
    - **Format Compatibility**: Data **must** be saved in a format compatible with `lerobot` to ensure seamless integration.

### 2.3 Cameras
- **Preview**: Real-time video stream preview in the UI.
- **Depth Cameras**:
    - Visualize depth map (if applicable).
    - Calibration tools for intrinsic/extrinsic parameters.

## 3. UI/UX Design

## 3. UI/UX Design

### 3.1 Hardware Dashboard (`/hardware`)
- **Philosophy**: Show *only* managed (added) devices.
- **Layout**:
    - **Header**: "Hardware" Title + "Add Device" Button.
    - **Category Tabs**: [All] | [Robots] | [Cameras].
    - **Grid**: Cards for each added device.
- **Card Design**:
    - **Header**: Icon + Friendly Name + Status Badge (Online/Offline).
    - **Body**: ID Snippet, Key Labels (e.g., `role: leader`).
    - **Primary Actions**:
        - "Control" (for Robots) / "View" (for Cameras).
    - **Secondary Actions (Triple Dot)**:
        - "Settings" (Edit Name/Labels).
        - "Calibrate" (for Robots and depth cameras).
        - "Remove" (Removes from `list.json`. Prompt user: "Also delete calibration data?").

### 3.2 Add Device Workflow
1.  **Discovery List**: Clicking "Add Device" navigates to a list of *detected but un-added* devices.
    - *If ID is missing, show as disabled/unsupported.*
2.  **Selection**: User clicks a device to configure it.
3.  **Setup/Edit Modal** (Also used for "Settings"):
    - **Metadata**: Name Input, Label Editor (with category-specific defaults).
    - **Connection Settings**: 
        - **Baud Rate**: Dropdown (e.g., 115200, 1000000). *Crucial for verification to work.*
        - **Model**: Editable Dropdown (Combobox). **Allows custom input** for unsupported/custom robots, or selection from a preset list (e.g., "myCobot 280").
    - **URDF/Model Settings**: Dropdown to select model type or upload custom URDF.
    - **Verification Panel**:
        - **Camera**: Live video stream.
        - **Robot**: **Live 3D Pose**. Requires correct Baud Rate and Model to work.
    - **Action**: "Add Device" / "Save".

### 3.3 Dedicated Operation Pages
Instead of a single complex "Detail Page", functionalities are split:
- **Common Features**: 
    - **Debug Console**: A collapsible bottom panel showing raw logs/commands (essential for troubleshooting).
- **Control Page** (`/hardware/:id/control`):
    - **Calibration Warning**: If `calibration.json` is missing, display a prominent warning banner: "Device uncalibrated. Accuracy may be affected."
    - **Arms**: 3D Gizmo Control, Joint Sliders, XYZ Input.
    - **Cameras**: Full-screen stream.
- **Calibration Page** (`/hardware/:id/calibrate`):
    - Wizard-style interface for performing calibration.
- **Settings**: Handled via the Setup/Edit Modal on the dashboard.

## 4. Technical Architecture

### 4.1 Backend
- **Language**: Python (leveraging existing stack).
- **Service**: `HardwareManager` singleton.
- **Libraries**:
    - **Discovery**: 
        - **Robots (Serial)**: `pyserial.tools.list_ports` (Polling) used universally.
        - **Cameras (Video)**: OS-specific handling required for Serial Numbers **and Metadata (Vendor, Model)**:
            - **Linux**: Parsing `/dev/v4l/by-id/` filenames (format: `bus-Manufacturer_Product_Serial-video-index`).
            - **Windows**: Querying WMI `Win32_PnPEntity` properties (`Caption`, `Manufacturer`, `DeviceID`).
            - **macOS**: Parsing JSON output of `system_profiler` (fields: `_name`, `manufacturer_id`).
    - **Camera Stream**: `opencv-python` for standard view.
    - **Camera**: `opencv-python` for standard streams, vendor SDKs for depth.
    - **Communication**: REST API or WebSocket for real-time status/control.

### 4.2 Data Storage
- **Format**: JSON files.
- **Directory Structure**:
  ```text
  ~/.leropilot/
    └── hardwares/
        ├── list.json                 # Global registry of known devices
        ├── robot/
        │   └── <unique_id>/
        │       ├── calibration.json  # Device-specific heavy data
        │       └── custom.urdf       # Optional uploaded URDF
        └── camera/
            └── <unique_id>/
                └── calibration.json
  ```
- **Schemas**:
  1. **`list.json`** (Index):
     ```json
     [
       {
         "id": "USB123456",
         "category": "robot",      // Enum: "robot", "camera"
         "name": "My Robot Arm",
         "manufacturer": "Elephant Robotics", // Metadata from discovery
         "model": "mechArm 270",              // Metadata from discovery
         "labels": {
            "leropilot.ai/role": "leader",
            "leropilot.ai/position": "left"
         },
         "created_at": "2023-10-27T10:00:00Z",
         // Settings: Driver/Connection specific parameters
         "settings": { 
            "baud_rate": 115200  // Example for Robots. Cameras might have "resolution".
         }
       }
     ]
     ```

## 6. Implementation Strategy
> [!IMPORTANT]
> **Proof of Concept (PoC) Requirement**
> Before starting the full implementation, the following PoCs must be completed to validate technical feasibility:
> 1.  **Hardware Discovery**: Verify that `pyserial` and OS-specific camera methods can reliably retrieve **Serial Numbers** and **Metadata** (Vendor/Model) across platforms.
> 2.  **3D Visualization**: Verify that the frontend stack (React + Three.js) can successfully **render URDF files** and allow **Gizmo-based interaction** (drag to move).
  2. **`calibration.json`** (Specific Data):
     ```json
     {
       // Must follow the schema required by the 'lerobot' library.
       // Example (subject to verification):
       "intrinsic": [...],
       "extrinsic": [...],
       "joint_offsets": [...]
     }
     ```

## 5. Risks, Difficulties & Solutions

### 5.1 Linux USB Permissions (The `sudo` Issue)
- **Problem**: On Linux, accessing raw USB/Serial devices (files in `/dev/`) usually requires `root` privileges. Running the entire app as sudo is dangerous and bad practice.
- **Solution**: **`udev` Rules**.
    - **What it is**: `udev` is the Linux device manager. It supports "rules" files that tell the kernel "when a device matching X is plugged in, do Y".
    - **Implementation**:
        1. **Primary Method (`pkexec`)**:
            - The backend uses `pkexec` to securely escalate privileges and copy the rule file to `/etc/udev/rules.d/`.
            - This provides a native system dialog for password entry.
        2. **Missing `pkexec` Fallback**:
            - If `pkexec` is not found, the UI prompts the user to install it:
                - Debian/Ubuntu: `sudo apt-get install policykit-1`
                - Fedora/CentOS: `sudo dnf install polkit`
                - Arch: `sudo pacman -S polkit`
            - **Alternative**: Provide a **Broad Rule** to minimize future updates.
                - The UI displays a broad rule content (e.g., matching the `tty` subsystem widely or a range of vendors) and instructions:
                - "Run the following command to create a permissive rule file:"
                - `echo 'SUBSYSTEM=="tty", MODE="0666"' | sudo tee /etc/udev/rules.d/99-leropilot-broad.rules && sudo udevadm control --reload`
                - *Note*: Warn the user that this is less secure but avoids repeated prompts.

### 5.2 Missing Unique IDs
- **Problem**: Some cheap USB-to-Serial chips (e.g., clone CH340) lack unique serial numbers. They all report "0000" or null.
- **Solution**: **Drop Support**.
    - Devices without a unique serial number **cannot be added** to the system.
    - Usage of such devices prevents reliable identification and management. The UI will show these devices as "Unsupported (No Unique ID)" in the discovered list, but the "Add" button will be disabled.

### 5.3 Acquiring ID Failures
- **Problem**: Sometimes the OS recognizes a device but fails to read descriptors due to power issues or driver glitches.
- **Solution**:
    - Retry logic in the discovery loop.
    - Show as "Unknown/Malfunctioning Device" in UI with a "Retry" button.

### 5.4 Hot-plugging
- **Problem**: Devices can be plugged/unplugged at any time.
- **Solution**:
    - Use `pyudev` monitors (Linux) to listen for kernel events (`add`, `remove`).
    - Use polling (e.g., every 2s) on Windows/macOS if event-based listening is complex to implement cross-platform (though looking for libraries like `pnp` is better). `pyserial.tools.list_ports` is fast enough for polling every few seconds.
