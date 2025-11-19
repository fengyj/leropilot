# Environment Management Design

## 1. Overview

This feature allows users to create and manage isolated LeRobot environments. It handles:

- **Dependency Management**: Using `uv` for fast, reliable installs.
- **Source Management**: Cloning/Updating LeRobot from official or custom Git repositories.
- **Dependency Management**: Using `uv` for fast, reliable installs.
- **Source Management**: Cloning/Updating LeRobot from official or custom Git repositories.
- **Hardware Adaptation**: Auto-detecting GPU and recommending PyTorch versions.
- **Customization**: Installing specific robot support (extras) and FFmpeg versions.

## 2. Technical Architecture

### 2.1 `uv` Integration

- **Binary Management**:
  - **Bundled**: The `uv` binary (specific to the target OS) will be downloaded during the **build process** and bundled inside the application executable (PyInstaller).
  - **Runtime**: The app extracts/locates this bundled binary at runtime, ensuring `uv` is always available without network requests.
  - **Fallback**: If the bundled binary fails, we fall back to looking for a system-installed `uv`.
- **Usage**:
  - Create venv: `uv venv .venv --python <version>`
  - Install deps: `uv pip install -r requirements.txt` or `uv pip install .[extra]`
  - Mirror Config: Pass `--index-url` or set `UV_INDEX_URL` env var based on user config.

### 2.2 PyTorch & GPU Detection

- **Detection Strategy**:
  - **NVIDIA**: Run `nvidia-smi` to get the **Driver Version**.
  - **AMD**: Run `rocm-smi` or check for `/dev/kfd` to detect **ROCm Version**.
  - **CUDA/ROCm Compatibility**: Map Driver/System Version to the _maximum supported CUDA/ROCm version_.
  - **Apple Silicon**: Check `platform.machine() == 'arm64'` and `platform.system() == 'Darwin'`.
  - **CPU**: Fallback if no GPU detected.
- **Version Recommendation Logic**:
  1.  **Fetch Compatibility Map**: Try to fetch `compatibility.json` from the official LeRoPilot repository.
  2.  **Analyze Software Constraints**:
      - Fetch `pyproject.toml` from the selected LeRobot version (via `RepoManager`).
      - Parse `requires-python` (e.g., `">=3.10"`) to filter Python dropdown options.
      - Parse `dependencies` to find `torch` constraints (e.g., `">=2.1"`).
  3.  **Analyze Hardware Constraints**:
      - Detect GPU Driver and max supported CUDA/ROCm.
  4.  **Intersection (Recommendation)**:
      - Recommend the _highest_ PyTorch version that satisfies **BOTH** Hardware limits and Software constraints.
      - If no intersection exists (e.g., New GPU requires Torch 2.4, but LeRobot requires <2.2), warn the user and prioritize Hardware (so it runs), but mark as "Potential Incompatibility".

### 2.3 LeRobot Versioning & Source Management

- **Repository Caching**:
  - To support multiple repositories (official, forks, custom), we maintain a cache directory at `~/.leropilot/cache/repos/`.
  - Each unique Repository URL is hashed to create a separate bare Git repository (e.g., `~/.leropilot/cache/repos/<md5_of_url>`).
  - This ensures that different forks or repositories do not conflict with each other.
  - Environment creation clones from this local cache to the environment's `src` directory, ensuring speed and offline capability.
  - Checkout the specific Ref (Branch/Tag).
- **Version Selection**:
  - Backend lists all local branches and tags from the Cache.
  - Default selection: `main` (or `master`).
  - User can select a specific tag (e.g., `v1.5`) or branch.

### 2.4 FFmpeg Management (Cross-Platform)

- **Strategy**:
  - **Download on Demand**: Binaries are downloaded to `~/.leropilot/cache/ffmpeg/<version>/<platform>/`.
  - **Network Mitigation**: To support users with restricted network access (e.g., in China), users can manually place the FFmpeg binary in this cache directory if the automatic download fails.
  - **Installation**: The binary is **copied** (not symlinked) to the environment's `bin` directory (or `Scripts` on Windows) to ensure isolation and avoid permission issues on all platforms.
- **Platform Specifics**:
  - **Windows**: `ffmpeg.exe` -> `Scripts/ffmpeg.exe`
  - **Linux/macOS**: `ffmpeg` -> `bin/ffmpeg` (ensure `chmod +x`)

### 2.5 Custom Robot Support

- **Challenge**: Users may have custom hardware not listed in LeRobot's official extras.
- **Solution**:
  - **"Custom / Base Install" Option**: Added to the Robot Selection list.
  - **Effect**: Installs only the base `lerobot` dependencies without any specific robot extras.
  - **Post-Install**: Users can manually install drivers via the terminal or `uv pip install`.
  - **Custom Code**: Users can point the "Repository" setting to their own fork of LeRobot if their custom robot code resides there.

### 2.6 Log Management

- **Persistence**:
  - All installation command outputs (stdout and stderr) are captured and written to `~/.leropilot/envs/<id>/install.log`.
  - This file persists after installation for troubleshooting.
- **Real-time Streaming**:
  - The backend streams these logs in real-time to the frontend via Server-Sent Events (SSE) at `/environments/{id}/install_logs`.
  - The UI displays this stream in a terminal-like view during the "Installation Progress" step.

### 2.7 Robustness & Error Handling

- **Path Safety**:
  - All file paths (especially on Windows) will be properly quoted in generated scripts to handle spaces (e.g., `C:\Program Files\...`).
  - The application will strictly use `pathlib` for all internal path manipulations.
- **Permission Checks**:
  - On startup, the app will verify write access to `~/.leropilot`.
  - If `uv` or `ffmpeg` binaries are not executable (Linux/macOS), the app will attempt `chmod +x` and fail gracefully with a clear error if denied.
- **Dependency Validation**:
  - **Git**: The app uses `shutil.which("git")` to find git in the system `PATH` (equivalent to `where git` on Windows or `which git` on Linux).
  - If missing, the "First Run" screen will block progress until the user provides a valid path.
  - **UV**: Bundled with the app. No user action required.
- **Network Resilience**:
  - All network operations (git clone, pip install) will have configurable timeouts.
  - Users can configure global proxies or mirrors in the Settings page.

## 3. Data Models

### 3.1 `EnvironmentConfig` (Stored in `config.json` inside env dir)

```python
class EnvironmentConfig(BaseModel):
    id: str # UUID
    name: str # Virtual environment folder name (filesystem safe, unique)
    display_name: str # User-friendly name (unique)
    created_at: datetime

    # Source
    repo_url: str # The actual git URL used (e.g., "https://github.com/huggingface/lerobot")
    ref: str  # tag, branch, or commit
    commit_hash: str # resolved commit

    # Python / UV
    python_version: str # e.g., "3.10"

    # Hardware
    torch_version: str # e.g., "2.4.0+cu121"
    cuda_version: Optional[str]
    rocm_version: Optional[str]

    # Extras
    selected_robots: List[str] # e.g., ["aloha", "xarm"]
```

    data_dir: Path = "~/.leropilot"
    # Map of Alias -> Git URL
    known_repos: Dict[str, str] = {
        "official": "https://github.com/huggingface/lerobot"
    }
    default_repo: str = "official"
    # ... other settings

````

### 3.2 `compatibility.json` Schema (Hosted in Repo)

```json
{
  "torch_versions": [
    {
      "version": "2.4.0",
      "flavor": "cu121",
      "cuda_version": "12.1",
      "rocm_version": null,
      "python_versions": ["3.10", "3.11"],
      "is_recommended": true
    },
    {
      "version": "2.4.0",
      "flavor": "rocm6.1",
      "cuda_version": null,
      "rocm_version": "6.1",
      "python_versions": ["3.10", "3.11"],
      "is_recommended": true
    }
  ],
  "driver_to_cuda": {
    "535": "12.2",
    "550": "12.4"
  },
  "driver_to_rocm": {
    "6.1.0": "6.1"
  }
}
````

## 4. UI Design & User Flow

### 4.0 Frontend Technology Stack

- **Framework**: React 18 (Vite) + TypeScript.
- **Styling**: Tailwind CSS (v3.4+).
- **Components**: Headless UI / Radix UI for accessible primitives, styled with Tailwind.
- **Icons**: Lucide React.
- **State Management**: Zustand.

### 4.1 Global Configuration (First Run / Settings)

**Context**: Occurs on the very first launch or when accessing the "Settings" page.
**Goal**: Ensure the host system is ready for creating environments.

- **Welcome Screen (First Run)**:
  - "Welcome to LeRoPilot. Let's set up your workspace."
- **Configuration Fields**:
  1.  **Data Directory**: Where environments and cache will be stored.
      - Default: `~/.leropilot`
      - Action: Browse/Change.
  2.  **Git Configuration**:
      - Status: "Detected at /usr/bin/git" or "Not Found".
      - Option: "Use System Git" or "Specify Path".
  3.  **Network / Mirrors** (Optional):
      - **PyPI Mirror**: e.g., `https://pypi.tuna.tsinghua.edu.cn/simple` (Crucial for CN users).
      - **HF/Git Mirror**: URL prefix for accelerating model/code downloads.
- **Action**: "Save & Continue".
  - Backend validates paths and permissions.
  - Downloads `uv` if missing.

### 4.2 Environment Creation Wizard (Standard Flow)

**Context**: User clicks "Create Environment" on the main dashboard.
**Pre-condition**: Global config is valid.

#### Step 1: Source Selection

- **Fields**:
  - **Repository**: Dropdown [Official (HuggingFace/LeRobot)] | [Custom URL].
  - **Version**: Dropdown [v2.0] | [v1.0] | [main] | [Custom Ref].
- **Action**: "Next" -> Triggers backend to fetch metadata (available extras).

#### Step 2: Hardware & Environment

- **Python Version**: Dropdown [3.10] (Recommended) | [3.11].
- **Hardware**:
  - Detected: "NVIDIA RTX 4090 (CUDA 12.1)"
  - PyTorch Version: Dropdown [2.4.0+cu121 (Recommended)] | [2.3.0] | [CPU].
- **Mirror**: Input (Pre-filled from global config, editable).

#### Step 3: Robot Support (Extras)

- **Dynamic List**: Checkboxes generated from `pyproject.toml`.
  - [ ] Aloha
  - [ ] PushT
  - [ ] XArm
- **Note**: "Selecting robots will install additional dependencies."

#### Step 4: Review & Advanced (Script Edit)

- **Summary View**: Shows selected Repo, Python, PyTorch, and Extras.
- **"Advanced: Edit Install Script"**: Toggle button.
  - **Action**: Calls backend to generate the install script based on current selections.
  - **Platform Adaptation**:
    - **Linux/macOS**: Generates a Bash script (`install.sh`).
    - **Windows**: Generates a PowerShell script (`install.ps1`) or Batch script (`install.bat`).
  - **UI**: A code editor showing the generated commands.
  - **User Capability**: User can modify flags, add environment variables, or insert custom commands.
- **"Create Environment"**:
  - If script was edited, sends the _custom script_ to the backend.
  - If not, sends the _structured config_.

#### Step 5: Installation Progress

- Progress bar with detailed log view (terminal-like).
- Streaming logs from the executing script.

### 4.3 User Guidance & Tooltips

**Goal**: Assist non-technical users in making correct choices.

- **General Strategy**: Use "Recommended" badges and Info icons (ℹ️) with hover tooltips.
- **Specific Guidance**:
  - **Python Version**:
    - _Tooltip_: "LeRobot works best with Python 3.10. Newer versions might have compatibility issues."
  - **Hardware Detection**:
    - _Display_: "Detected: NVIDIA RTX 3090"
    - _Tooltip_: "We detected your GPU driver (v535.12). This determines which PyTorch versions you can run."
  - **PyTorch Version**:
    - _Recommended Tag_: "Recommended for your Hardware & LeRobot v2.0"
    - _Tooltip (on Recommended)_: "This version is fully compatible with your NVIDIA Driver and the selected LeRobot code."
    - _Tooltip (on Disabled/Warning)_: "This version requires a newer GPU driver than what you have installed. Please update your NVIDIA driver to use it."
  - **Robot Extras**:
    - _Tooltip_: "Select the specific robot hardware you are using to install necessary drivers and control libraries."

## 5. Implementation Plan

### Phase 1: Backend Core

1.  Implement `UVManager` to handle `uv` binary and commands.
2.  Implement `GPUDetection` service.
3.  Implement `RepoInspector` to parse `pyproject.toml` from git refs.
4.  Implement `InstallPlanGenerator`:
    - Input: `EnvironmentConfig`
    - Output: `str` (Shell script)
5.  Update `EnvironmentInstaller` to accept either `EnvironmentConfig` (auto-generate plan) or `raw_script` (user modified).

### Phase 2: API Updates

1.  Update `POST /environments` to accept multi-step config or add a validation/introspection endpoint `POST /environments/inspect`.

### Phase 3: Frontend UI

1.  Refactor `CreateEnvironmentDialog` into a Wizard (`Steps` component).
2.  Integrate introspection API.
3.  Implement real-time log streaming (already in spec, just ensure it works with `uv` output).
