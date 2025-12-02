````markdown
# Settings & Configuration Management Reference (for AI)

> This document is the authoritative guide for AI-driven maintenance, upgrade, and extension of the LeRoPilot settings and configuration subsystem. It covers architecture, data models, persistence, validation, Git tool management, upgrade strategies, and code generation principles. Any code or configuration changes must conform to this specification.

---

## 1. Core Principles & Architecture

### 1.1 Goals

- Provide unified, type-safe configuration management across frontend and backend.
- Support platform-specific defaults (Windows/macOS/Linux) while allowing user customization.
- Enable runtime configuration changes without application restart (except server settings).
- Ensure configuration persistence and validation for data integrity.
- Support environment variable overrides for deployment flexibility.

### 1.2 System Structure

- **Backend**: Python (FastAPI), Pydantic v2 models for validation.
- **Frontend**: React + TypeScript, form-based settings UI with live preview.
- **Persistence**: YAML files in platform-specific config directories.
- **Communication**: REST API for config CRUD operations.

### 1.3 Key Modules (Backend)

- `models/config.py`: Pydantic data models for all configuration sections.
- `config.py`: ConfigManager singleton for loading, saving, and environment variable overrides.
- `routers/config.py`: FastAPI endpoints for configuration operations.
- `core/git_manager.py`: Git tool installation, bundled Git management, version detection.

### 1.4 Key Modules (Frontend)

- `pages/settings-page.tsx`: Main settings UI with live preview and validation.
- `components/repository-status-button.tsx`: Repository download/update status display.
- `contexts/theme-context.tsx`: Theme management with live switching.
- `locales/*.json`: Static UI element translations (labels, buttons, tooltips, etc.).

---

## 2. Configuration Data Models

### 2.1 Model Hierarchy

```python
AppConfig
├── server: ServerConfig
├── ui: UIConfig
├── paths: PathsConfig
├── tools: ToolsConfig
│   └── git: ToolSource
├── repositories: RepositoriesConfig
├── pypi: PyPIConfig
├── huggingface: HuggingFaceConfig
└── advanced: AdvancedConfig
```

### 2.2 Configuration Sections

#### ServerConfig

**Purpose**: HTTP server runtime settings.

**Fields**:

- `port` (int): Server port, default `8000`
- `host` (str): Bind address, default `"127.0.0.1"`
- `auto_open_browser` (bool): Auto-open browser on startup, default `True`

**Environment Override**: `LEROPILOT_SERVER_PORT`, `LEROPILOT_SERVER_HOST`, `LEROPILOT_SERVER_AUTO_OPEN_BROWSER`

**Constraints**:

- Port must be 1024-65535
- Changes require application restart

**UI Location**: Not exposed in settings UI (internal configuration)

---

#### UIConfig

**Purpose**: User interface preferences.

**Fields**:

- `theme` (Literal["system", "light", "dark"]): Color theme, default `"system"`
- `preferred_language` (Literal["en", "zh"]): UI language, default `"en"`

**Environment Override**: `LEROPILOT_UI_THEME`, `LEROPILOT_UI_PREFERRED_LANGUAGE`

**Constraints**:

- Theme must be one of: `system`, `light`, `dark`
- Language must be one of: `en`, `zh`

**UI Behavior**:

- **Live Preview**: Theme and language changes apply immediately without saving
- **Cleanup on Cancel**: Reverts to saved values if user navigates away without saving
- **Unsaved Indicator**: Shows amber badge when current value differs from saved

**UI Location**: Appearance and Language cards in settings page

---

#### PathsConfig

**Purpose**: Directory paths for data storage.

**Fields**:

- `data_dir` (Path): Root data directory, platform-specific defaults:
  - Windows: `%APPDATA%/leropilot`
  - macOS: `~/Library/Application Support/leropilot`
  - Linux: `~/.config/leropilot`
- `repos_dir` (Path): Repository cache, derived from `data_dir/repos` (read-only)
- `environments_dir` (Path): Virtual environments, derived from `data_dir/environments` (read-only)
- `logs_dir` (Path): Application logs, derived from `data_dir/logs` (read-only)
- `cache_dir` (Path): Temporary files and downloads, derived from `data_dir/cache` (read-only)

**Environment Override**: `LEROPILOT_PATHS_DATA_DIR`

**Constraints**:

- `data_dir` can ONLY be changed if no environments have been created
- If environments exist, attempting to change `data_dir` returns HTTP 400 with error message
- `~` expands to user home directory
- Derived paths (repos_dir, environments_dir, logs_dir, cache_dir) are computed automatically

**Migration Behavior**:

- When `data_dir` changes (and no environments exist):
  1. Create new `data_dir`
  2. Migrate subdirectories: `logs/`, `cache/`, `repos/`
  3. Use `shutil.copytree(dirs_exist_ok=True)` for merging
  4. Clean up empty old directory

**UI Behavior**:

- `data_dir`: Editable input (locked with visual indicator if environments exist)
- Other paths: Read-only gray inputs
- Lock tooltip: "Cannot change data directory after environments have been created. This is to prevent data loss and ensure data integrity."

**UI Location**: Paths card in settings page

---

#### ToolsConfig

**Purpose**: External tool (Git) source configuration.

**Fields**:

- `git` (ToolSource): Git executable source

**ToolSource Model**:

```python
class ToolSource(BaseModel):
    type: Literal["bundled", "custom"]
    custom_path: str | None = None
```

**Constraints**:

- When `type == "bundled"`: Use application-bundled tool
- When `type == "custom"`: `custom_path` must be a valid executable path
- Custom paths are validated on change (see Git validation below)

**Environment Override**: Not supported (tools are runtime-specific)

**Notes**:

- **UV**: Not configurable by users. UV is managed by the system and installed via CI/CD.
- UV version is specified in GitHub Actions workflows (`.github/workflows/*.yml`) using `astral-sh/setup-uv@v*` action.
- To update UV version: Update the `setup-uv` action version in all workflow files.

**UI Location**: Tools card in settings page (Git only)

---

#### RepositoriesConfig

**Purpose**: LeRobot repository sources and version defaults.

**Fields**:

- `lerobot_sources` (list[RepositorySource]): Available repository sources
- `default_branch` (str): Default Git branch, default `"main"`
- `default_version` (str): Default release version, default `"v2.0"`

**RepositorySource Model**:

```python
class RepositorySource(BaseModel):
    id: str        # Unique identifier (UUID for custom repos, "official" for default)
    name: str      # Display name (e.g., "Official")
    url: str       # Git repository URL
    is_default: bool  # Whether this is the default source
```

**Constraints**:

- At least one source with `is_default == True`
- Default source cannot be deleted or edited
- Custom sources can be added/removed/set as default
- URLs must be valid Git repository URLs

**Environment Override**: Not supported (user-managed list)

**UI Behavior**:

- Default source: Shows "Default" badge, name/URL read-only, delete button hidden
- Custom sources: Editable name/URL, "Set as Default" button, delete button
- "Set as Default": Marks clicked source as default, unmarks others
- Repository download/update: Shows status button only for saved sources with valid URLs
- Status button shows: download icon (not downloaded), update icon (updates available), checkmark (up to date)

**UI Location**: LeRobot Repositories card in settings page

---

#### PyPIConfig

**Purpose**: Python Package Index mirror configuration for package installation.

**Fields**:

- `mirrors` (list[PyPIMirror]): Available PyPI mirrors (can be empty)

**PyPIMirror Model**:

```python
class PyPIMirror(BaseModel):
    name: str     # Display name (e.g., "Tsinghua Mirror", "Aliyun Mirror")
    url: str      # Mirror URL (e.g., "https://pypi.tuna.tsinghua.edu.cn/simple")
    enabled: bool # Whether this mirror is currently enabled (default False)
```

**Constraints**:

- `mirrors` list can be empty (no mirrors configured)
- At most one mirror can have `enabled == True` at any time
- If no mirror is enabled, official PyPI is used
- URLs must be valid HTTP(S) URLs ending with `/simple`

**Environment Override**: Not supported (user-managed list)

**Installation Behavior**:

- When no mirror is enabled (default):
  - UV uses official PyPI: `uv pip install <package>`
  - No `--index-url` parameter added
  - Best for users with good connection to PyPI
- When a mirror is enabled:
  - UV uses the enabled mirror: `uv pip install <package> --index-url <mirror_url>`
  - Applied to all `uv pip install` commands except PyTorch (which has its own index)
  - Useful for users in regions with slow PyPI access (e.g., China)

**UI Behavior**:

- **Status Display**: Shows current state at top:
  - "Using Official PyPI (no mirror enabled)" - when all mirrors disabled
  - "Current Mirror: <name>" - when a mirror is enabled
- **Mirror List**: All configured mirrors shown with:
  - Name and URL inputs (editable)
  - "Enable" button (if not enabled) - clicking enables this mirror and disables others
  - "Disable" button (if enabled) - clicking returns to official PyPI
  - "Delete" button - removes mirror from list
- **Visual Feedback**: Enabled mirror has blue background/border to stand out
- **Add Mirror Button**: Creates new mirror with `enabled=False`

**Common Mirrors** (for reference):

- Tsinghua: `https://pypi.tuna.tsinghua.edu.cn/simple`
- Aliyun: `https://mirrors.aliyun.com/pypi/simple/`
- Douban: `https://pypi.douban.com/simple/`
- USTC: `https://pypi.mirrors.ustc.edu.cn/simple/`

**Note**: Official PyPI (`https://pypi.org/simple`) is the default source used when no mirror is enabled.

**UI Location**: PyPI Mirrors card in settings page

---

#### HuggingFaceConfig

**Purpose**: HuggingFace Hub integration settings.

**Fields**:

- `token` (str): HuggingFace API token, default `""`
- `cache_dir` (str): Model cache directory, default `""`

**Environment Override**: `LEROPILOT_HUGGINGFACE_TOKEN`, `LEROPILOT_HUGGINGFACE_CACHE_DIR`

**Constraints**:

- Token is optional (public models work without token)
- If provided, token should be valid HF token format

**Security**:

- Token should be masked in UI (password input)
- Never log token values
- Consider using system keyring for production

**UI Location**: HuggingFace card in settings page (not yet implemented in current version)

---

#### AdvancedConfig

**Purpose**: Advanced technical settings.

**Fields**:

- `installation_timeout` (int): Max seconds for environment installation, default `3600` (1 hour)
- `log_level` (Literal["INFO", "DEBUG", "TRACE"]): Logging verbosity, default `"INFO"`

**Environment Override**: `LEROPILOT_ADVANCED_INSTALLATION_TIMEOUT`, `LEROPILOT_ADVANCED_LOG_LEVEL`

**Constraints**:

- `installation_timeout` must be positive integer (recommended: 1800-7200)
- `log_level` must be one of: `INFO`, `DEBUG`, `TRACE`

**UI Behavior**:

- Timeout: Number input with description of impact
- Log level: Select dropdown with descriptions:
  - INFO: Standard logging (production)
  - DEBUG: Detailed logging (troubleshooting)
  - TRACE: Very verbose logging (development)

**UI Location**: Advanced card in settings page

---

## 3. Configuration Persistence & Loading

### 3.1 File Location

**Platform-specific config paths**:

- **Windows**: `%APPDATA%/leropilot/config.yaml`
- **macOS**: `~/Library/Application Support/leropilot/config.yaml`
- **Linux**: `~/.config/leropilot/config.yaml`

**Path resolution** (in `config.py`):

```python
def get_config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", "~"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux
        base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config"))
    return (base / "leropilot" / "config.yaml").expanduser()
```

### 3.2 Loading Flow

```
1. Load YAML file (if exists) → dict
2. Parse dict → AppConfig (Pydantic validation)
3. Apply environment variable overrides → final AppConfig
4. Initialize derived paths (repos_dir, environments_dir, etc.)
5. Create directories if they don't exist
```

**Environment Variable Override Format**:

- Pattern: `LEROPILOT_<SECTION>_<KEY>`
- Example: `LEROPILOT_SERVER_PORT=9000`
- Section names: `SERVER`, `UI`, `PATHS`, `TOOLS`, `ADVANCED`
- Nested fields use `_` separator (e.g., `LEROPILOT_TOOLS_GIT_TYPE`)

**Type Conversion**:

- Strings: Direct assignment
- Integers: `int(value)`
- Booleans: `value.lower() in ("true", "1", "yes")`
- Paths: `Path(value).expanduser()`

### 3.3 Saving Flow

```
1. Convert AppConfig → dict (Pydantic model_dump)
2. Convert Path objects → strings
3. Write dict → YAML file (atomic write with temp file)
4. Reload config to ensure consistency
```

**Path Serialization**:

- All `Path` objects converted to strings
- Relative to home directory where appropriate
- Platform-specific path separators

**Atomic Write**:

```python
temp_path = config_path.with_suffix(".yaml.tmp")
temp_path.write_text(yaml_content)
temp_path.replace(config_path)  # Atomic rename
```

### 3.4 Default Initialization

When no `config.yaml` exists (first-time user):

1. Create `AppConfig()` with all defaults
2. **Load preset configuration** from `resources/default_config.json`:
   - Preset PyPI mirrors (Chinese mirrors for better accessibility)
   - Preset repositories (if applicable)
3. Compute platform-specific `data_dir`
4. Initialize all derived paths
5. Create directory structure
6. Save to disk

**Preset Configuration File** (`src/leropilot/resources/default_config.json`):

```json
{
  "pypi_mirrors": [
    {
      "name": "Tsinghua University/清华大学",
      "url": "https://pypi.tuna.tsinghua.edu.cn/simple",
      "enabled": false
    },
    {
      "name": "Aliyun/阿里云",
      "url": "https://mirrors.aliyun.com/pypi/simple/",
      "enabled": false
    },
    {
      "name": "USTC/中国科技大学",
      "url": "https://pypi.mirrors.ustc.edu.cn/simple/",
      "enabled": false
    }
  ],
  "repositories": [
    {
      "name": "Official/官方仓库",
      "url": "https://github.com/huggingface/lerobot.git",
      "is_default": true
    }
  ]
}
```

**Preset Loading Logic**:

```python
def _apply_preset_config(self, config: AppConfig) -> AppConfig:
    """Apply preset configuration for first-time users."""
    preset_path = Path(__file__).parent / "resources" / "default_config.json"
    if not preset_path.exists():
        return config

    with open(preset_path) as f:
        preset_data = json.load(f)

    # Apply preset PyPI mirrors (only if user has no mirrors)
    if not config.pypi.mirrors and "pypi_mirrors" in preset_data:
        config.pypi.mirrors = [
            PyPIMirror(name=m["name"], url=m["url"], enabled=m.get("enabled", False))
            for m in preset_data["pypi_mirrors"]
        ]

    # Apply preset repositories (only if default only)
    # ...

    return config
```

**Benefits**:

- First-time users get common Chinese mirrors pre-configured
- Reduces setup friction for users in China
- Users can still add/remove/modify mirrors as needed
- No impact on existing users (only applies when config doesn't exist)

**Directory Creation**:

```python
def model_post_init(self, __context: Any) -> None:
    # Compute derived paths
    self.repos_dir = self.data_dir / "repos"
    self.environments_dir = self.data_dir / "environments"
    self.logs_dir = self.data_dir / "logs"
    self.cache_dir = self.data_dir / "cache"

    # Create directories
    for path in [self.data_dir, self.repos_dir,
                 self.environments_dir, self.logs_dir,
                 self.cache_dir]:
        path.mkdir(parents=True, exist_ok=True)
```

---

## 4. Git Tool Management

### 4.1 Git Source Types

**Bundled Git**:

- Application downloads and manages Git internally
- Installed to `{data_dir}/tools/git/`
- Platform-specific binaries:
  - **Windows**: Portable Git from official releases (MinGit)
  - **macOS**: Git from official macOS installer or Homebrew
  - **Linux**: Git from official Git SCM builds

**Custom Git**:

- User provides path to existing Git installation
- Can be system Git (`/usr/bin/git`) or custom location
- Path validation on input (see below)

### 4.2 Bundled Git Installation Strategy

**Detection**:

```python
def get_bundled_git_path() -> Path | None:
    """Get path to bundled Git executable."""
    git_tool_dir = config.paths.data_dir / "tools" / "git"

    if sys.platform == "win32":
        git_exe = git_tool_dir / "cmd" / "git.exe"
    else:
        git_exe = git_tool_dir / "bin" / "git"

    return git_exe if git_exe.exists() else None
```

**Installation Sources**:

| Platform | Source                   | Format  | URL Pattern                                                                                                         |
| -------- | ------------------------ | ------- | ------------------------------------------------------------------------------------------------------------------- |
| Windows  | Git for Windows (MinGit) | .7z     | `https://github.com/git-for-windows/git/releases/download/v{version}.windows.1/MinGit-{version}-busybox-64-bit.zip` |
| macOS    | Official Git installer   | .dmg    | `https://sourceforge.net/projects/git-osx-installer/files/git-{version}-intel-universal-mavericks.dmg/download`     |
| Linux    | Git SCM tarball          | .tar.xz | `https://mirrors.edge.kernel.org/pub/software/scm/git/git-{version}.tar.xz`                                         |

**Version Detection** (to get latest stable):

1. **GitHub API**: Query `https://api.github.com/repos/git/git/tags` for official releases
2. **Parse versions**: Extract version numbers (e.g., `v2.43.0`)
3. **Filter stable**: Exclude `-rc` (release candidates) and `-beta` versions
4. **Sort**: Use semantic versioning comparison
5. **Select latest**: Pick highest version number

**Example API Response Parsing**:

```python
async def get_latest_stable_git_version() -> str:
    """Fetch latest stable Git version from GitHub API."""
    url = "https://api.github.com/repos/git/git/tags"
    response = await httpx.get(url)
    tags = response.json()

    # Extract version numbers
    versions = []
    for tag in tags:
        name = tag["name"]  # e.g., "v2.43.0"
        if name.startswith("v") and "-" not in name:
            # Remove 'v' prefix and parse
            version = name[1:]
            versions.append(version)

    # Sort by semantic version
    from packaging.version import parse as parse_version
    versions.sort(key=parse_version, reverse=True)

    return versions[0]  # Latest stable
```

**Installation Flow**:

1. Detect platform and architecture
2. Fetch latest stable version from GitHub API
3. Construct download URL based on platform
4. Download archive to `{cache_dir}/git-{version}.{ext}`
5. Extract to `{data_dir}/tools/git/`
6. Verify installation: run `git --version`
7. Update config: set `tools.git.type = "bundled"`

**Streaming Download with Progress**:

```python
async def download_bundled_git(progress_callback: Callable[[str, int], None]) -> None:
    """Download and install bundled Git with progress reporting."""
    version = await get_latest_stable_git_version()
    url = construct_download_url(sys.platform, version)

    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url) as response:
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(cache_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    progress = int(downloaded / total * 100)
                    await progress_callback(f"Downloading Git {version}", progress)

    # Extract and verify...
    await progress_callback("Extracting...", 90)
    extract_archive(cache_path, install_dir)

    await progress_callback("Verifying installation...", 95)
    verify_git_installation(install_dir)

    await progress_callback("Complete", 100)
```

**UI Integration**:

- Show download button when bundled Git not installed
- Progress bar during download/extraction
- Real-time status messages via Server-Sent Events (SSE)
- Auto-refresh status after installation

### 4.3 Git Path Validation

**Validation Steps** (for custom Git):

1. Check if path is a command name (like `"git"`) → resolve with `shutil.which()`
2. If not found in PATH, treat as absolute/relative path
3. Verify file exists
4. Verify it's a regular file (not directory)
5. Verify executable permissions (Unix: `os.access(path, os.X_OK)`)
6. Execute `git --version` and parse output
7. Return validation result with version string

**API Endpoint**: `POST /api/config/tools/git/validate`

**Request**:

```json
{
  "path": "/usr/bin/git" // or "git" for auto-detection
}
```

**Response (Success)**:

```json
{
  "valid": true,
  "version": "git version 2.43.0"
}
```

**Response (Failure)**:

```json
{
  "valid": false,
  "error": "Path does not exist"
}
```

**UI Behavior**:

- **On Input**: Clear validation state
- **On Blur**: Trigger validation API call
- **Show Icon**:
  - Loading spinner during validation
  - Green checkmark + version tooltip on success
  - Red X + error tooltip on failure
- **Auto-detect Button**: Calls validation with `"git"` to find system Git

### 4.4 Git Version Updates

**When to Update**:

- New stable Git release announced (monitor GitHub releases)
- Security vulnerabilities discovered in current version
- Critical bug fixes in new version
- User requests specific version

**Update Procedure**:

1. **Detect New Version**:

   ```python
   current_version = parse_git_version(bundled_git_path)
   latest_version = await get_latest_stable_git_version()

   if parse_version(latest_version) > parse_version(current_version):
       # Update available
       pass
   ```

2. **Notify User** (optional, in future version):

   - Show notification in UI
   - Include version number and changelog link
   - Provide "Update" button

3. **Download New Version**:

   - Same process as initial installation
   - Download to `{cache_dir}/git-{new_version}.{ext}`

4. **Backup Old Version** (optional):

   ```python
   old_dir = data_dir / "tools" / "git"
   backup_dir = data_dir / "tools" / f"git-{current_version}-backup"
   old_dir.rename(backup_dir)
   ```

5. **Install New Version**:

   - Extract to `{data_dir}/tools/git/`
   - Verify installation
   - Clean up old backup (if verified)

6. **Rollback on Failure**:
   ```python
   if not verify_git_installation(new_git_path):
       new_dir.rmdir()
       backup_dir.rename(old_dir)
       raise Exception("Git update failed, rolled back to previous version")
   ```

**Testing Checklist**:

- [ ] Git version detection works
- [ ] Download and extraction succeeds
- [ ] `git --version` returns expected version
- [ ] Can clone repositories
- [ ] Can fetch/pull updates
- [ ] Works with LeRobot environment creation

**Metadata Maintenance**:

- Update `docs/git_installation_strategy.md` with version update procedures
- Document any breaking changes or compatibility issues
- Add version to release notes

### 4.5 UV Version Management

**UV is NOT user-configurable**. UV is managed by the CI/CD pipeline and installed via GitHub Actions.

**Current UV Management**:

- UV is installed in GitHub Actions workflows using `astral-sh/setup-uv` action
- Version is specified in workflow YAML files (e.g., `setup-uv@v4`)
- Users and developers don't need to manually install or configure UV

**Updating UV Version**:

1. **Check for New UV Release**:

   - Visit: https://github.com/astral-sh/uv/releases
   - Check for latest stable release (exclude pre-releases)
   - Review release notes for breaking changes

2. **Update Workflow Files**:

   - Find all workflow files that use `setup-uv` action:
     ```bash
     grep -r "astral-sh/setup-uv" .github/workflows/
     ```
   - Update action version in all files:

     ```yaml
     # Before
     - uses: astral-sh/setup-uv@v3

     # After
     - uses: astral-sh/setup-uv@v4
     ```

3. **Files to Update** (typical locations):

   - `.github/workflows/build.yml` - Main build workflow
   - `.github/workflows/test.yml` - Test workflow
   - `.github/workflows/release.yml` - Release workflow
   - Any other custom workflows using UV

4. **Test Workflow Changes**:

   - Create a test branch
   - Push changes to trigger CI
   - Verify all workflows succeed
   - Check that UV commands work as expected

5. **Update Documentation**:
   - Update `README.md` if it mentions UV version
   - Update `CONTRIBUTING.md` with new UV version requirements
   - Add note to release notes

**Example Update PR**:

```markdown
## Update UV to v0.5.0

### Changes

- Updated `astral-sh/setup-uv` action from v3 to v4 in all workflows
- UV version: 0.4.x → 0.5.0

### Testing

- [x] Build workflow passes
- [x] Test workflow passes
- [x] Release workflow tested (dry run)
- [x] Environment creation works with new UV

### Breaking Changes

None (backward compatible)

### References

- UV Release Notes: https://github.com/astral-sh/uv/releases/tag/0.5.0
```

**Why UV is Not User-Configurable**:

- UV is used for virtual environment creation and package installation
- Consistent UV version across all installations ensures reproducibility
- Bundling UV would increase application size significantly
- UV updates are frequent and well-tested by Astral team
- System-level UV (via GitHub Actions or user's PATH) is sufficient

---

## 5. Configuration API Endpoints

### 5.1 Core Configuration Operations

#### GET /api/config

**Purpose**: Retrieve current configuration.

**Response**: `AppConfig` model (JSON)

**Example**:

```json
{
  "server": { "port": 8000, "host": "127.0.0.1", "auto_open_browser": true },
  "ui": { "theme": "system", "preferred_language": "en" },
  "paths": { "data_dir": "/home/user/.config/leropilot", ... },
  "tools": { "git": { "type": "bundled", "custom_path": null }, ... },
  "repositories": { "lerobot_sources": [...], ... },
  "pypi": { "mirrors": [...] },
  "huggingface": { "token": "", "cache_dir": "" },
  "advanced": { "installation_timeout": 3600, "log_level": "INFO" }
}
```

---

#### PUT /api/config

**Purpose**: Update configuration with validation.

**Request Body**: `AppConfig` model (JSON)

**Response**: Updated `AppConfig` model

**Validation**:

1. Check if `data_dir` is being changed
2. If changed, verify no environments exist → HTTP 400 if environments exist
3. Migrate data if `data_dir` changed (and no environments)
4. Validate all fields via Pydantic
5. Save to disk
6. Reload and return updated config

**Error Response** (400):

```json
{
  "detail": "Cannot change data directory after environments have been created. This is to prevent data loss and ensure data integrity."
}
```

**Error Response** (500):

```json
{
  "detail": "Failed to save config: <error details>"
}
```

---

#### POST /api/config/reset

**Purpose**: Reset configuration to defaults, preserving `data_dir` if environments exist.

**Response**: Reset `AppConfig` model

**Logic**:

1. Check if environments exist
2. Create default `AppConfig()`
3. If environments exist, preserve current `data_dir`
4. Reinitialize derived paths
5. Save to disk
6. Return new config

---

#### POST /api/config/reload

**Purpose**: Reload configuration from disk (discard unsaved changes).

**Response**: Reloaded `AppConfig` model

**Use Case**: Revert to saved state without restart.

---

#### GET /api/config/has-environments

**Purpose**: Check if any virtual environments have been created.

**Response**:

```json
{
  "has_environments": true
}
```

**Logic**: Check if `{data_dir}/environments/` contains any subdirectories.

**Use Case**: Determine if `data_dir` can be changed.

---

### 5.2 Git Tool Endpoints

#### GET /api/config/tools/git/bundled/status

**Purpose**: Get bundled Git installation status.

**Response (Installed)**:

```json
{
  "installed": true,
  "path": "/home/user/.config/leropilot/tools/git/bin/git",
  "version": "git version 2.43.0"
}
```

**Response (Not Installed)**:

```json
{
  "installed": false,
  "message": "Bundled Git is not installed."
}
```

**Response (Error)**:

```json
{
  "installed": false,
  "error": "Failed to get Git version: <stderr>"
}
```

---

#### GET /api/config/tools/git/bundled/download

**Purpose**: Download and install bundled Git with real-time progress.

**Response**: Server-Sent Events (SSE) stream

**Event Format**:

```
data: {"message": "Downloading Git 2.43.0", "progress": 45}\n\n
data: {"message": "Extracting...", "progress": 90}\n\n
data: DONE\n\n
```

**Error Event**:

```
data: ERROR: Failed to download: Connection timeout\n\n
```

**Post-Installation**:

- Updates config to set `tools.git.type = "bundled"`
- Saves config to disk

**Client Handling**:

```typescript
const eventSource = new EventSource("/api/config/tools/git/bundled/download");

eventSource.onmessage = (event) => {
  if (event.data === "DONE") {
    eventSource.close();
    // Refresh status
    return;
  }

  if (event.data.startsWith("ERROR:")) {
    eventSource.close();
    // Show error
    return;
  }

  const data = JSON.parse(event.data);
  setProgress(data); // { message, progress }
};
```

---

#### POST /api/config/tools/git/validate

**Purpose**: Validate Git executable path.

**Request**:

```json
{
  "path": "/usr/bin/git"
}
```

**Response**: See section 4.3 Git Path Validation.

---

#### GET /api/config/tools/git/which

**Purpose**: Get system Git path (auto-detect).

**Response**:

```json
{
  "path": "/usr/bin/git"
}
```

**Error (404)**:

```json
{
  "detail": "Git not found in PATH"
}
```

**Use Case**: Auto-detect button in custom Git path input.

---

### 5.3 Repository Management Endpoints

#### GET /api/config/repositories/{repo_id}/status

**Purpose**: Get repository download status and check for updates.

**Response**:

```json
{
  "repo_id": "official",
  "is_downloaded": true,
  "last_updated": "1703980800000", // Unix timestamp (ms)
  "cache_path": "/home/user/.config/leropilot/cache/repos/official",
  "has_updates": false
}
```

**Update Detection**:

1. Run `git fetch origin` in repo directory
2. Compare local HEAD with remote HEAD
3. If different, `has_updates = true`

---

#### POST /api/config/repositories/{repo_id}/download

**Purpose**: Clone or update repository to global cache.

**Response (Success)**:

```json
{
  "success": true,
  "action": "downloaded", // or "updated"
  "repo_id": "official",
  "commit_hash": "abc123...",
  "cache_path": "/home/user/.config/leropilot/cache/repos/official",
  "message": "Repository downloaded successfully"
}
```

**Error (404)**:

```json
{
  "detail": "Repository not found"
}
```

**Error (400 - Git not available)**:

```json
{
  "detail": "Git is not installed or not found in PATH. Please configure Git in Settings."
}
```

**Error (500)**:

```json
{
  "detail": "Failed to download/update repository: <error details>"
}
```

**Git Availability Check**:

```python
git_exec = git_manager._get_git_executable()
if git_exec == "git":
    if not shutil.which("git"):
        raise HTTPException(status_code=400, detail="Git not installed...")
else:
    if not Path(git_exec).exists() or not os.access(git_exec, os.X_OK):
        raise HTTPException(status_code=400, detail=f"Invalid Git path: {git_exec}...")
```

---

#### GET /api/config/repositories/{repo_id}/download/stream

**Purpose**: Stream repository download progress (for large repos).

**Response**: Server-Sent Events (SSE) stream

**Event Format**:

```
data: Cloning into '/path/to/repo'...\n\n
data: Receiving objects: 45% (123/456)\n\n
data: DONE\n\n
```

**Error Event**:

```
data: ERROR: Repository not found\n\n
data: ERROR: Git not installed\n\n
```

**Use Case**: Real-time progress for large repository clones.

---

## 6. UI Interaction Patterns

### 6.1 Live Preview System

**Theme Changes**:

```typescript
// Apply immediately via ThemeContext
useEffect(() => {
  if (config?.ui.theme) {
    setAppTheme(config.ui.theme);
  }
}, [config?.ui.theme]);

// Cleanup on unmount (if not saved)
useEffect(() => {
  return () => {
    if (savedConfig && currentConfig) {
      if (savedConfig.ui.theme !== currentConfig.ui.theme) {
        setAppTheme(savedConfig.ui.theme); // Revert
      }
    }
  };
}, [savedConfig, currentConfig]);
```

**Language Changes**:

```typescript
// Apply immediately via i18n
useEffect(() => {
  const applyLanguageChange = async () => {
    const targetLang = config?.ui.preferred_language;
    if (!targetLang) return;

    // Skip if already on target language
    if (
      i18n.language === targetLang ||
      i18n.language.startsWith(targetLang + "-")
    ) {
      return;
    }

    await i18n.changeLanguage(targetLang);
    setForceRender((prev) => prev + 1); // Force UI update
  };

  applyLanguageChange();
}, [config?.ui.preferred_language]);

// Cleanup on unmount (if not saved)
useEffect(() => {
  return () => {
    if (savedConfig && currentConfig) {
      if (
        savedConfig.ui.preferred_language !==
        currentConfig.ui.preferred_language
      ) {
        i18n.changeLanguage(savedConfig.ui.preferred_language); // Revert
      }
    }
  };
}, [savedConfig, currentConfig]);
```

**Benefits**:

- Immediate visual feedback
- No need to save to preview
- Automatic cleanup if user cancels

---

### 6.2 Unsaved Changes Indicator

**Detection**:

```typescript
const hasUnsavedChanges = (section: "theme" | "language") => {
  if (!config || !savedConfig) return false;

  if (section === "theme") {
    return config.ui.theme !== savedConfig.ui.theme;
  }

  if (section === "language") {
    return config.ui.preferred_language !== savedConfig.ui.preferred_language;
  }

  return false;
};
```

**Visual Indicator**:

```tsx
{
  hasUnsavedChanges("theme") && (
    <span className="rounded border border-amber-900/50 bg-amber-900/20 px-2 py-1 text-xs font-medium text-amber-500">
      {t("settings.unsavedChanges")}
    </span>
  );
}
```

---

### 6.3 Validation Feedback

**Git Path Validation**:

```tsx
<div className="relative">
  <input
    type="text"
    value={config.tools.git.custom_path || ""}
    onChange={(e) => {
      setConfig({
        ...config,
        tools: {
          ...config.tools,
          git: { ...config.tools.git, custom_path: e.target.value },
        },
      });
      // Clear validation state
      setGitPathError(null);
      setGitPathValidation(null);
    }}
    onBlur={async (e) => {
      // Validate on blur
      const path = e.target.value;
      if (!path) return;

      setGitPathValidating(true);
      const response = await fetch("/api/config/tools/git/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      const data = await response.json();

      if (data.valid) {
        setGitPathValidation(data.version);
        setGitPathError(null);
      } else {
        setGitPathError(data.error);
        setGitPathValidation(null);
      }
      setGitPathValidating(false);
    }}
    className={cn(
      "w-full border px-3 py-2 rounded-md",
      gitPathError && "border-red-500",
      !gitPathError && config.tools.git.custom_path && "border-green-500"
    )}
  />

  {/* Validation icon */}
  <div className="absolute top-1/2 right-3 -translate-y-1/2">
    {gitPathValidating && <Loader2 className="h-4 w-4 animate-spin" />}
    {gitPathError && (
      <XCircle className="h-4 w-4 text-red-500" title={gitPathError} />
    )}
    {gitPathValidation && (
      <CheckCircle2
        className="h-4 w-4 text-green-500"
        title={gitPathValidation}
      />
    )}
  </div>
</div>
```

---

### 6.4 Repository Status Button

**Component**: `repository-status-button.tsx`

**States**:

1. **Not Downloaded**: Download icon, "Download" text
2. **Downloading**: Progress spinner, "Downloading..." text
3. **Downloaded (No Updates)**: Checkmark icon, "Up to date" text
4. **Downloaded (Updates Available)**: Update icon, "Update Available" text
5. **Updating**: Progress spinner, "Updating..." text

**Behavior**:

```typescript
const handleAction = async () => {
  if (!status.is_downloaded) {
    // Start download
    setDownloading(true);
    await fetch(`/api/config/repositories/${repoId}/download`, {
      method: "POST",
    });
    // Refresh status
    fetchStatus();
  } else if (status.has_updates) {
    // Start update
    setDownloading(true);
    await fetch(`/api/config/repositories/${repoId}/download`, {
      method: "POST",
    });
    fetchStatus();
  }
  setDownloading(false);
};
```

**Visual States**:

- Not downloaded: Blue button with download icon
- Downloading: Disabled button with spinner
- Up to date: Green button with checkmark (disabled)
- Updates available: Orange button with update icon
- Error: Red button with error icon

---

### 6.5 Form Validation

**Path Lock Validation**:

```tsx
<input
  type="text"
  value={config.paths.data_dir}
  onChange={(e) =>
    setConfig({
      ...config,
      paths: { ...config.paths, data_dir: e.target.value },
    })
  }
  disabled={hasEnvironments}
  className={cn(
    "w-full border px-3 py-2 rounded-md",
    hasEnvironments && "opacity-60 cursor-not-allowed bg-gray-100"
  )}
/>;

{
  hasEnvironments && (
    <p className="text-xs text-amber-600 mt-1">
      {t("settings.paths.dataDirLocked")}
    </p>
  );
}
```

**Backend Validation** (on save):

```python
if current_config.paths.data_dir != config.paths.data_dir:
    has_envs = await check_has_environments()
    if has_envs:
        raise HTTPException(
            status_code=400,
            detail="Cannot change data directory after environments have been created."
        )
```

---

## 7. Configuration Upgrade & Migration

### 7.1 Version Detection

**Approach**: Add `config_version` field to `AppConfig`:

```python
class AppConfig(BaseModel):
    config_version: int = 1  # Current schema version
    server: ServerConfig
    # ... other fields
```

**Version Checks** (in ConfigManager.load()):

```python
def load(self) -> AppConfig:
    data = yaml.safe_load(config_path.read_text())
    version = data.get("config_version", 0)

    if version < 1:
        data = migrate_v0_to_v1(data)

    if version < 2:
        data = migrate_v1_to_v2(data)

    # ... continue with loading
    return AppConfig(**data)
```

---

### 7.2 Migration Strategies

#### Adding New Fields

**Scenario**: New field `server.cors_origins` added in v2.

**Strategy**: Pydantic default values handle this automatically:

```python
class ServerConfig(BaseModel):
    port: int = 8000
    host: str = "127.0.0.1"
    auto_open_browser: bool = True
    cors_origins: list[str] = []  # New field with default
```

**No migration needed** - existing configs get default value.

---

#### Removing Fields

**Scenario**: Field `ui.font_size` removed in v2.

**Migration Function**:

```python
def migrate_v1_to_v2(data: dict) -> dict:
    """Remove deprecated font_size field."""
    if "ui" in data and "font_size" in data["ui"]:
        del data["ui"]["font_size"]

    data["config_version"] = 2
    return data
```

---

#### Renaming Fields

**Scenario**: `paths.data_directory` renamed to `paths.data_dir` in v2.

**Migration Function**:

```python
def migrate_v1_to_v2(data: dict) -> dict:
    """Rename data_directory to data_dir."""
    if "paths" in data:
        if "data_directory" in data["paths"]:
            data["paths"]["data_dir"] = data["paths"].pop("data_directory")

    data["config_version"] = 2
    return data
```

---

#### Restructuring Sections

**Scenario**: `tools.git_path` (string) changed to `tools.git` (ToolSource object) in v2.

**Migration Function**:

```python
def migrate_v1_to_v2(data: dict) -> dict:
    """Convert git_path string to git ToolSource object."""
    if "tools" in data and "git_path" in data["tools"]:
        old_path = data["tools"].pop("git_path")

        if old_path:
            # Had custom path
            data["tools"]["git"] = {
                "type": "custom",
                "custom_path": old_path
            }
        else:
            # Was using bundled
            data["tools"]["git"] = {
                "type": "bundled",
                "custom_path": None
            }

    data["config_version"] = 2
    return data
```

---

### 7.3 Breaking Changes

**When to Introduce**:

- Only when absolutely necessary (security, major refactor)
- Document thoroughly in release notes
- Provide clear migration path

**Breaking Change Checklist**:

1. Increment `config_version`
2. Write migration function
3. Add unit tests for migration
4. Update documentation
5. Add release notes entry
6. Test migration with real configs (from previous versions)

**Example Release Note**:

```markdown
## v2.0.0 - Breaking Changes

### Configuration Schema Changes

The configuration schema has been updated to v2. Old configs will be automatically migrated on first load.

**Changes**:

- `paths.data_directory` → `paths.data_dir`
- `tools.git_path` (string) → `tools.git` (object with `type` and `custom_path`)
- Removed `ui.font_size` (no longer used)

**Migration**: Automatic on first load. Your old config will be backed up to `config.yaml.v1.bak`.

**Action Required**: None (automatic). If you use environment variables:

- `LEROPILOT_PATHS_DATA_DIRECTORY` → `LEROPILOT_PATHS_DATA_DIR`
- `LEROPILOT_TOOLS_GIT_PATH` → `LEROPILOT_TOOLS_GIT_CUSTOM_PATH` (and set `LEROPILOT_TOOLS_GIT_TYPE=custom`)
```

---

### 7.4 Backup & Rollback

**Backup on Migration**:

```python
def load(self) -> AppConfig:
    data = yaml.safe_load(config_path.read_text())
    version = data.get("config_version", 0)

    if version < CURRENT_VERSION:
        # Backup before migration
        backup_path = config_path.with_suffix(f".yaml.v{version}.bak")
        shutil.copy(config_path, backup_path)
        logger.info(f"Backed up config to {backup_path}")

        # Migrate
        data = migrate_to_latest(data)

        # Save migrated config
        self.save(AppConfig(**data))

    return AppConfig(**data)
```

**Manual Rollback** (if migration fails):

```bash
# User action
cd ~/.config/leropilot
cp config.yaml.v1.bak config.yaml
```

---

## 8. Security & Best Practices

### 8.1 Secrets Management

**Current State**: HuggingFace token stored in plain text YAML.

**Recommendations**:

1. **Environment Variables** (current approach):

   ```bash
   export LEROPILOT_HUGGINGFACE_TOKEN="hf_..."
   ```

   - Pros: Not in config file, easily rotated
   - Cons: Visible in process list, not encrypted

2. **System Keyring** (future enhancement):

   ```python
   import keyring

   # Store
   keyring.set_password("leropilot", "huggingface_token", token)

   # Retrieve
   token = keyring.get_password("leropilot", "huggingface_token")
   ```

   - Pros: OS-level encryption, secure storage
   - Cons: Platform-specific, requires additional dependency

3. **Encrypted Config** (future enhancement):
   - Encrypt sensitive fields in YAML
   - Use key derived from machine ID or user password
   - Decrypt on load

**Action Item**: Document current approach and recommend keyring for production.

---

### 8.2 Input Validation

**Path Validation**:

```python
from pathlib import Path

def validate_path(path_str: str) -> Path:
    """Validate and resolve path."""
    path = Path(path_str).expanduser().resolve()

    # Prevent directory traversal
    if ".." in path.parts:
        raise ValueError("Path traversal not allowed")

    # Ensure writable (for data_dir)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    if not os.access(path, os.W_OK):
        raise ValueError("Path is not writable")

    return path
```

**URL Validation**:

```python
from urllib.parse import urlparse

def validate_url(url: str) -> str:
    """Validate URL format."""
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https", "git"):
        raise ValueError("Invalid URL scheme")

    if not parsed.netloc:
        raise ValueError("Invalid URL: no domain")

    return url
```

**Executable Validation**:

```python
def validate_executable(path: str) -> Path:
    """Validate executable path."""
    path = Path(path)

    if not path.exists():
        raise ValueError(f"Executable not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    if not os.access(path, os.X_OK):
        raise ValueError(f"Path is not executable: {path}")

    return path
```

---

### 8.3 Error Handling

**Configuration Loading Errors**:

```python
def load(self) -> AppConfig:
    try:
        if not self.config_path.exists():
            return self._create_default_config()

        data = yaml.safe_load(self.config_path.read_text())
        config = AppConfig(**data)
        self._apply_env_overrides(config)
        return config

    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in config file: {e}")
        # Backup corrupted file
        backup = self.config_path.with_suffix(".yaml.corrupt.bak")
        shutil.copy(self.config_path, backup)
        logger.info(f"Backed up corrupted config to {backup}")
        # Return default
        return self._create_default_config()

    except ValidationError as e:
        logger.error(f"Config validation failed: {e}")
        # Backup invalid file
        backup = self.config_path.with_suffix(".yaml.invalid.bak")
        shutil.copy(self.config_path, backup)
        # Return default
        return self._create_default_config()
```

**API Error Responses**:

```python
@router.put("/config")
async def update_config(config: AppConfig) -> AppConfig:
    try:
        # ... validation and save
        return config

    except HTTPException:
        raise  # Re-raise HTTP exceptions

    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "Invalid configuration",
                "details": e.errors()
            }
        )

    except Exception as e:
        logger.exception("Unexpected error saving config")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_ERROR",
                "message": "Failed to save configuration",
                "details": str(e)
            }
        )
```

---

## 9. Testing Requirements

### 9.1 Unit Tests

**Config Loading**:

```python
def test_load_config_creates_default_if_not_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        manager = ConfigManager(config_path)

        config = manager.load()

        assert config_path.exists()
        assert config.server.port == 8000
        assert config.ui.theme == "system"
```

**Environment Overrides**:

```python
def test_env_override_server_port(monkeypatch):
    monkeypatch.setenv("LEROPILOT_SERVER_PORT", "9000")

    manager = ConfigManager()
    config = manager.load()

    assert config.server.port == 9000
```

**Path Validation**:

```python
def test_data_dir_change_blocked_when_environments_exist():
    # Create environment
    env_dir = config.paths.environments_dir / "test-env"
    env_dir.mkdir(parents=True)

    # Try to change data_dir
    new_config = config.model_copy(deep=True)
    new_config.paths.data_dir = Path("/tmp/new-data")

    with pytest.raises(HTTPException) as exc_info:
        update_config(new_config)

    assert exc_info.value.status_code == 400
    assert "Cannot change data directory" in exc_info.value.detail
```

---

### 9.2 Integration Tests

**Config Save/Load Cycle**:

```python
def test_config_persistence():
    manager = ConfigManager()

    # Modify config
    config = manager.load()
    config.ui.theme = "dark"
    config.advanced.log_level = "DEBUG"

    # Save
    manager.save(config)

    # Reload
    new_config = manager.load()

    assert new_config.ui.theme == "dark"
    assert new_config.advanced.log_level == "DEBUG"
```

**Migration Tests**:

```python
def test_migration_v1_to_v2():
    # Create v1 config
    v1_config = {
        "config_version": 1,
        "paths": {
            "data_directory": "/old/path"  # Old field name
        }
    }

    # Save as YAML
    config_path.write_text(yaml.dump(v1_config))

    # Load (should auto-migrate)
    manager = ConfigManager(config_path)
    config = manager.load()

    assert config.config_version == 2
    assert config.paths.data_dir == Path("/old/path")
```

---

### 9.3 E2E Tests (Playwright)

**Settings Page Tests**:

```typescript
test("theme change applies live preview", async ({ page }) => {
  await page.goto("/settings");

  // Click dark theme
  await page.click('button:has-text("Dark")');

  // Check theme applied (without saving)
  const html = await page.locator("html");
  await expect(html).toHaveClass(/dark/);

  // Navigate away without saving
  await page.goto("/");

  // Return to settings
  await page.goto("/settings");

  // Theme should be reverted
  await expect(html).not.toHaveClass(/dark/);
});

test("save config persists changes", async ({ page }) => {
  await page.goto("/settings");

  // Change theme
  await page.click('button:has-text("Dark")');

  // Save
  await page.click('button:has-text("Save")');

  // Wait for success message
  await expect(page.locator("text=Settings saved")).toBeVisible();

  // Reload page
  await page.reload();

  // Theme should persist
  const html = await page.locator("html");
  await expect(html).toHaveClass(/dark/);
});
```

---

## 10. AI Maintenance Workflows

### 10.1 Adding New Configuration Options

**Workflow**:

1. **Add to Pydantic Model** (`models/config.py`):

   ```python
   class AdvancedConfig(BaseModel):
       installation_timeout: int = 3600
       log_level: Literal["INFO", "DEBUG", "TRACE"] = "INFO"
       # New field
       enable_telemetry: bool = False
   ```

2. **Update Environment Override Support** (`config.py`):

   ```python
   # Automatic if using standard naming
   # LEROPILOT_ADVANCED_ENABLE_TELEMETRY=true
   ```

3. **Add to Frontend UI** (`settings-page.tsx`):

   ```tsx
   <div>
     <label>Enable Telemetry</label>
     <input
       type="checkbox"
       checked={config.advanced.enable_telemetry}
       onChange={(e) =>
         setConfig({
           ...config,
           advanced: { ...config.advanced, enable_telemetry: e.target.checked },
         })
       }
     />
   </div>
   ```

4. **Add i18n Strings**:

   **Frontend** (`locales/en.json`, `locales/zh.json`) - Static UI elements only:

   ```json
   {
     "settings": {
       "advanced": {
         "enableTelemetry": "Enable Telemetry",
         "enableTelemetryDescription": "Help improve LeRoPilot by sharing anonymous usage data"
       }
     }
   }
   ```

   **Backend** (`src/leropilot/resources/i18n.json`) - Dynamic content (installation steps, extras, etc.):

   - Only needed if the new config affects environment installation or dynamic content
   - Not applicable for most settings UI changes

5. **Write Tests**:

   - Unit test: Default value
   - Unit test: Environment override
   - E2E test: UI interaction

6. **Update Documentation**:
   - Add to this document (section 2.2)
   - Add to user documentation

---

### 10.2 Handling Breaking Changes

**Workflow**:

1. **Increment config_version** in `AppConfig`
2. **Write migration function**:

   ```python
   def migrate_v2_to_v3(data: dict) -> dict:
       """Migration for v3: restructure tools section."""
       # ... migration logic
       data["config_version"] = 3
       return data
   ```

3. **Update `ConfigManager.load()`**:

   ```python
   if version < 3:
       data = migrate_v2_to_v3(data)
   ```

4. **Add migration tests**
5. **Update documentation** with migration notes
6. **Write release notes** with clear user impact

---

### 10.3 Git Version Updates

**Automated Check** (to be implemented):

```python
async def check_for_git_updates() -> dict[str, str | bool]:
    """Check if Git update is available."""
    current = await get_bundled_git_version()  # From bundled install
    latest = await get_latest_stable_git_version()  # From GitHub API

    return {
        "current_version": current,
        "latest_version": latest,
        "update_available": parse_version(latest) > parse_version(current)
    }
```

**Manual Update Procedure**:

1. Run automated check or manually fetch latest version from GitHub API
2. Update `docs/git_installation_strategy.md` with new version
3. Test download URLs for all platforms
4. Update download logic in `core/git_manager.py` if needed
5. Test installation on all platforms
6. Run integration tests with new Git version
7. Create PR with changes
8. Add to release notes

**Future Enhancement**: Add "Check for Updates" button in UI that calls this endpoint and shows notification.

---

### 10.4 UV Version Updates

**Automated Check** (to be implemented):

```python
async def check_for_uv_updates() -> dict[str, str | bool]:
    """Check if UV update is available (for CI/CD maintenance)."""
    # Parse current version from workflow files
    workflow_path = Path(".github/workflows/build.yml")
    current = parse_setup_uv_version(workflow_path)

    # Fetch latest from GitHub API
    url = "https://api.github.com/repos/astral-sh/uv/releases/latest"
    response = await httpx.get(url)
    latest_release = response.json()
    latest = latest_release["tag_name"].lstrip("v")

    return {
        "current_version": current,
        "latest_version": latest,
        "update_available": parse_version(latest) > parse_version(current),
        "release_url": latest_release["html_url"]
    }
```

**Manual Update Procedure**:

1. Check for new UV release on GitHub: https://github.com/astral-sh/uv/releases
2. Review release notes for breaking changes or new features
3. Search for all `setup-uv` usage:
   ```bash
   grep -r "astral-sh/setup-uv" .github/workflows/
   ```
4. Update version in all workflow files (e.g., `@v3` → `@v4`)
5. Test workflows on a test branch
6. Verify environment creation still works
7. Create PR with changes and test results
8. Update `CONTRIBUTING.md` if needed
9. Add to release notes

**Monitoring**:

- Check UV releases periodically (monthly or when notified)
- Monitor Astral's UV announcements on Twitter/GitHub
- Subscribe to UV release notifications on GitHub

**Compatibility Considerations**:

- UV is generally backward compatible
- Python version support may change (check `requires-python` in UV)
- Command-line interface changes are rare but possible
- Test with oldest supported Python version (currently 3.10)

---

## 11. Key Files and Their Roles

### 11.1 Backend Files

| File                  | Purpose                                 | Maintenance                                 |
| --------------------- | --------------------------------------- | ------------------------------------------- |
| `models/config.py`    | Pydantic models for all config sections | Add/modify fields, update validators        |
| `config.py`           | ConfigManager singleton for persistence | Update loading/saving logic, add migrations |
| `routers/config.py`   | FastAPI endpoints for config operations | Add new endpoints, update validation        |
| `core/git_manager.py` | Git tool installation and management    | Update Git download URLs, version detection |

### 11.2 Frontend Files

| File                                      | Purpose                        | Maintenance                                    |
| ----------------------------------------- | ------------------------------ | ---------------------------------------------- |
| `pages/settings-page.tsx`                 | Main settings UI               | Add new config sections, update forms          |
| `components/repository-status-button.tsx` | Repository status display      | Update status detection logic                  |
| `contexts/theme-context.tsx`              | Theme management               | Update theme switching logic                   |
| `locales/*.json`                          | Static UI element translations | Add translations for labels, buttons, tooltips |

### 11.3 Configuration Files

| File                           | Location                     | Purpose                                                                   |
| ------------------------------ | ---------------------------- | ------------------------------------------------------------------------- |
| `default_config.json`          | `src/leropilot/resources/`   | Preset configuration for first-time users (PyPI mirrors, repositories)    |
| `i18n.json`                    | `src/leropilot/resources/`   | Dynamic content localization (installation steps, extras, error messages) |
| `config.yaml`                  | Platform-specific config dir | User configuration (runtime)                                              |
| `config.yaml.v*.bak`           | Platform-specific config dir | Backup before migration                                                   |
| `settings-config-reference.md` | `docs/for-ai-reference/`     | AI maintenance guide (this document)                                      |
| `git_installation_strategy.md` | `docs/`                      | Git installation details                                                  |

---

## 12. References

- [models/config.py](../../src/leropilot/models/config.py) - Configuration data models
- [config.py](../../src/leropilot/config.py) - ConfigManager implementation
- [routers/config.py](../../src/leropilot/routers/config.py) - Configuration API endpoints
- [settings-page.tsx](../../frontend/src/pages/settings-page.tsx) - Settings UI
- [git_installation_strategy.md](../git_installation_strategy.md) - Git installation details
- [environment-management-reference.md](./environment-management-reference.md) - Environment management reference

---

## 13. Changelog

### 2025-01-XX

- Initial version
- Comprehensive documentation of configuration subsystem
- Git tool management strategy
- UI interaction patterns
- Migration and upgrade workflows

---

**Version:** 2025-01-XX
**Maintainer:** LeRoPilot Team
````
