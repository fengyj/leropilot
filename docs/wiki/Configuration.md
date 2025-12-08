# Configuration

LeRoPilot provides a comprehensive settings interface to customize your experience. You can access the settings by clicking the **Settings** icon in the sidebar.

## General Settings

### Appearance

- **Theme**: Choose between **System** (follows OS), **Light**, or **Dark** mode.
- Changes are applied immediately.

### Language

- **UI Language**: Switch between **English** and **Chinese (简体中文)**.
- The interface updates instantly upon selection.

## Paths

### Data Directory

- **Location**: Specifies where LeRoPilot stores environments, datasets, and logs.
- **Default**: `~/.leropilot/data` (Linux/macOS) or `%USERPROFILE%\.leropilot\data` (Windows).
- You can change this to a custom location if you have limited space on your system drive.

### Read-Only Paths

- Add external directories that LeRoPilot can read from but not modify.
- Useful for accessing existing datasets without importing them.

## Tools

### Git Configuration

LeRoPilot requires Git for environment management. You can choose between:

1.  **Bundled Git (Recommended)**:

    - LeRoPilot can download and manage a portable version of Git.
    - Isolated from your system Git.
    - Ensures compatibility.
    - Click **"Download & Install"** to automatically set it up.

2.  **Custom Git**:
    - Use your system-installed Git.
    - Provide the path to the git executable (e.g., `/usr/bin/git`).
    - LeRoPilot will validate the version and path.

## Repositories

Configure where LeRoPilot fetches resources from.

- **LeRobot Sources**: Manage upstream repositories for LeRobot.
- **HuggingFace**: Configure HuggingFace Hub token and endpoint (useful for restricted networks).

## PyPI Mirrors

Configure Python package index mirrors to speed up environment creation.

- **Mirrors**: Add or remove PyPI mirrors (e.g., TUNA, Aliyun).
- **Primary**: Select the preferred mirror for installations.
