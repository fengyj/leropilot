# Environment Creation - Complete Design Specification

## Overview

This document provides a comprehensive specification for the LeRobot environment creation feature, covering both the UI implementation (completed) and backend requirements (to be implemented).

## User Flows

### 1. Standard Wizard Flow

**Path**: `/environments/new` → Wizard Steps → `/environments/install` → `/environments`

1. **Step 1: Repository Selection**

   - User selects from available repositories (Official/Custom)
   - Shows download status and last update time
   - Link to Settings > Repositories for adding custom repos

2. **Step 2: Version Selection**

   - User selects LeRobot version/tag
   - Shows release date and compatibility info

3. **Step 3: Hardware Configuration**

   - User selects Python version
   - User selects CUDA version (auto-detect, specific version, or CPU-only)

4. **Step 4: Extras Selection**

   - User selects optional robot support packages
   - Organized by categories (Robots, Tools)

5. **Step 5: Name Configuration**

   - User enters friendly name
   - Auto-generates environment ID
   - Option to customize ID

6. **Step 6: Review**

   - Shows summary of all selections
   - "Customize >" link to Advanced Installation
   - "Create" button to start installation

7. **Installation Page**
   - Real-time progress with expandable steps
   - Command view (read-only) with syntax highlighting
   - Log output with auto-scroll
   - Cancel/Retry/Reinstall/Done buttons based on state

### 2. Advanced Installation Flow

**Path**: `/environments/new` → Step 6 → "Customize >" → `/environments/advanced` → `/environments/install`

1. **Advanced Installation Page (Editor)**

   - Shows pre-generated installation steps based on wizard config
   - Each step has:
     - Editable command (shell script with syntax highlighting)
   - User can modify commands before installation
   - "Create" button saves custom steps and navigates to installation runner

2. **Installation with Custom Steps**
   - Uses custom commands from Advanced mode
   - Same UI as standard installation
   - Commands are read-only during installation

## UI Components

### CodeEditor Component

**Location**: `frontend/src/components/code-editor/code-editor.tsx`

**Features**:

- Syntax highlighting for shell/bash commands
- Read-only and editable modes
- Auto-height with max height (400px)
- Theme detection (light/dark)
- Line numbers
- Line wrapping

**Props**:

```typescript
interface CodeEditorProps {
  value: string;
  onChange?: (value: string) => void;
  language?: "shell" | "bash" | "powershell" | "javascript";
  readOnly?: boolean;
  height?: string;
  minHeight?: string;
  maxHeight?: string;
  placeholder?: string;
  className?: string;
}
```

### LogViewer Component

**Location**: `frontend/src/components/code-editor/log-viewer.tsx`

**Features**:

- Read-only log display
- Auto-scroll to bottom
- Auto-height with max height (400px)
- Theme detection
- Monospace font

**Props**:

```typescript
interface LogViewerProps {
  logs: string[];
  height?: string;
  minHeight?: string;
  maxHeight?: string;
  autoScroll?: boolean;
  className?: string;
}
```

## State Management

### Wizard Store

**Location**: `frontend/src/stores/environment-wizard-store.ts`

**State**:

```typescript
interface WizardConfig {
  repositoryId: string;
  repositoryName: string;
  lerobotVersion: string;
  pythonVersion: string;
  cudaVersion: string;
  extras: string[];
  envName: string;
  friendlyName: string;
}

interface AdvancedStep {
  id: string;
  name: string;
  comment: string | null;
  commands: string[];
  status: "pending" | "running" | "success" | "error";
  logs: string[];
}

interface WizardState {
  step: number;
  config: WizardConfig;
  customSteps: AdvancedStep[];
  setStep: (step: number) => void;
  updateConfig: (updates: Partial<WizardConfig>) => void;
  setCustomSteps: (steps: AdvancedStep[]) => void;
  reset: () => void;
}
```

### URL Synchronization

- Wizard step synced with URL query parameter: `?step=N`
- Supports browser back/forward navigation
- Initializes from URL on mount
- Updates URL when step changes via user interaction

## Installation Process Logic

### States

- **Pending**: Step not started
- **Running**: Step currently executing
- **Success**: Step completed successfully
- **Error**: Step failed
- **Cancelled**: User cancelled installation

### User Actions

#### 1. Cancel (During Installation)

- **Trigger**: User clicks "Cancel" button
- **Confirmation**: "确定要取消安装吗？"
- **Action**:
  - Stop current running step
  - Mark step as error with log: "Installation cancelled by user."
  - Set `isCancelled = true`
  - Show "Back" and "Reinstall" buttons

#### 2. Retry (After Error)

- **Condition**: Installation failed (error state, not cancelled)
- **Button**: "重试"
- **Action**:
  - Resume from first failed step
  - Reset failed step and all subsequent steps to pending
  - Clear logs for failed and subsequent steps
  - Start execution from failed step

#### 3. Reinstall (After Cancellation)

- **Condition**: Installation was cancelled by user
- **Button**: "重新安装"
- **Action**:
  - Perform cleanup (delete partial installation)
  - Reset ALL steps to pending
  - Clear all logs
  - Start execution from Step 1

#### 4. Back (After Cancellation)

- **Condition**: Installation was cancelled
- **Button**: "上一步"
- **Action**:
  - Trigger cleanup
  - Navigate back to wizard/advanced page
  - Allow user to modify configuration

#### 5. Done (After Success)

- **Condition**: All steps completed successfully
- **Button**: "完成"
- **Action**:
  - Navigate to `/environments`
  - Show new environment in list

### Progress Calculation

```typescript
const progress = Math.round(
  (steps.filter((s) => s.status === "success").length / steps.length) * 100
);
const isComplete =
  steps.length > 0 && steps.every((s) => s.status === "success");
```

## Internationalization

### Supported Languages

- English (`en.json`)
- Chinese (`zh.json`)

### Key Translation Sections

1. **Wizard Steps** (`wizard.steps.*`)
2. **Wizard Substeps** (`wizard.repo.*`, `wizard.version.*`, etc.)
3. **Wizard Buttons** (`wizard.buttons.*`)
4. **Advanced Installation** (`wizard.advanced.*`)
5. **Installation Process** (`wizard.installation.*`)
6. **Installation Steps** (`wizard.installation.stepsList.*`)

### Complete Coverage

All UI text is localized, including:

- Page titles and subtitles
- Button labels
- Step names
- Status messages
- Confirmation dialogs
- Help text and tooltips

## Theme Support

### Semantic CSS Classes

**Content Colors**:

- `text-content-primary` - Main text
- `text-content-secondary` - Descriptions
- `text-content-tertiary` - Hints/disabled

**Surface Colors**:

- `bg-surface-secondary` - Cards
- `bg-surface-tertiary` - Info boxes

**Border Colors**:

- `border-border-default` - Standard borders
- `border-border-subtle` - Subtle borders

**State Colors**:

- `text-success-content` / `bg-success-surface` - Success states
- `text-error-content` / `bg-error-surface` - Error states
- `text-blue-600` - Running/active states

### Component Theme Detection

Both `CodeEditor` and `LogViewer` automatically detect and adapt to theme changes:

```typescript
useEffect(() => {
  const isDark = document.documentElement.classList.contains("dark");
  setTheme(isDark ? "dark" : "light");

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.attributeName === "class") {
        const isDark = document.documentElement.classList.contains("dark");
        setTheme(isDark ? "dark" : "light");
      }
    });
  });

  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });

  return () => observer.disconnect();
}, []);
```

## Backend Requirements

### API Endpoints

#### 1. Get Available Repositories

```
GET /api/environments/repositories
Response: Repository[]
```

#### 2. Get Available Versions

```
GET /api/environments/repositories/{id}/versions
Response: Version[]
```

#### 3. Get Hardware Info

```
GET /api/environments/hardware
Response: HardwareInfo
```

#### 4. Get Available Extras

```
GET /api/environments/extras
Response: Extra[]
```

#### 5. Generate Installation Steps

```
POST /api/environments/generate-steps
Body: WizardConfig
Response: InstallStep[]
```

#### 6. Create Environment

**Standard Mode**:

```
POST /api/environments/create
Body: WizardConfig
Response: { installationId: string }
```

**Advanced Mode**:

```
POST /api/environments/create-advanced
Body: { env_config: WizardConfig, custom_steps: AdvancedStep[] }
Response: { installationId: string }
```

#### 7. Get Installation Status

```
GET /api/environments/installations/{id}
Response: InstallationStatus
```

#### 8. Cancel Installation

```
POST /api/environments/installations/{id}/cancel
Response: { success: boolean }
```

#### 9. Cleanup Environment

```
POST /api/environments/installations/{id}/cleanup
Response: { success: boolean }
```

### Real-time Communication

**WebSocket or Server-Sent Events** for streaming installation logs:

```
WS /api/environments/installations/{id}/logs
or
GET /api/environments/installations/{id}/logs/stream
```

**Message Format**:

```typescript
interface LogMessage {
  stepId: string;
  timestamp: string;
  content: string;
  level?: "info" | "warn" | "error";
}

interface StatusUpdate {
  stepId: string;
  status: "pending" | "running" | "success" | "error";
  progress?: number;
}
```

### Process Management

#### Command Execution

- Execute shell commands in isolated environment
- Capture stdout/stderr in real-time
- Support for cancellation (SIGTERM/SIGKILL)
- Timeout handling
- Error code detection

#### Environment Isolation

- Use virtual environments (venv/conda)
- Separate working directories
- Process group management for cleanup

#### Cleanup Operations

- Delete virtual environment directory
- Remove cloned repository
- Clean up temporary files
- Rollback on error (optional)

### Data Models

```python
class Repository:
    id: str
    name: str
    url: str
    is_downloaded: bool
    last_updated: Optional[datetime]

class Version:
    tag: str
    date: datetime
    is_stable: bool

class HardwareInfo:
    python_versions: List[str]
    cuda_versions: List[str]
    detected_cuda: Optional[str]
    has_nvidia_gpu: bool

class Extra:
    id: str
    name: str
    category: str
    description: str

class InstallStep:
    id: str
    name: str
    comment: str | None
    commands: List[str]
    status: str  # pending, running, success, error
    logs: List[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    exit_code: Optional[int]

class Installation:
    id: str
    config: dict
    steps: List[InstallStep]
    status: str  # pending, running, success, error, cancelled
    created_at: datetime
    completed_at: Optional[datetime]
```

### Error Handling

1. **Command Execution Errors**

   - Capture exit code
   - Include stderr in logs
   - Mark step as error
   - Allow retry

2. **Network Errors**

   - Retry with exponential backoff
   - Clear error messages
   - Fallback mirrors (for PyPI)

3. **Timeout Errors**

   - Configurable timeouts per step
   - Clear timeout messages
   - Allow manual retry

4. **Cleanup Errors**
   - Log cleanup failures
   - Don't block user flow
   - Provide manual cleanup instructions

### Security Considerations

1. **Command Injection Prevention**

   - Validate all user inputs
   - Use parameterized commands
   - Whitelist allowed commands in Advanced mode

2. **Path Traversal Prevention**

   - Validate environment names
   - Restrict to designated directories
   - Sanitize file paths

3. **Resource Limits**
   - Limit concurrent installations
   - Disk space checks
   - Memory limits for processes

## Testing Checklist

### UI Testing

- [ ] All wizard steps navigable
- [ ] URL sync works with browser back/forward
- [ ] Theme switching (light/dark)
- [ ] Language switching (en/zh)
- [ ] Responsive layout (mobile/tablet/desktop)
- [ ] Code editor syntax highlighting
- [ ] Log viewer auto-scroll
- [ ] All button states and actions

### Integration Testing

- [ ] Standard wizard flow end-to-end
- [ ] Advanced installation flow
- [ ] Installation cancellation
- [ ] Retry after error
- [ ] Reinstall after cancellation
- [ ] Cleanup on back navigation
- [ ] Real-time log streaming
- [ ] Multiple concurrent installations

### Error Scenarios

- [ ] Network failure during download
- [ ] Invalid command in Advanced mode
- [ ] Disk space exhaustion
- [ ] Process timeout
- [ ] Cleanup failure
- [ ] Backend unavailable

## Future Enhancements

1. **Installation Templates**

   - Save custom step configurations
   - Share templates between users
   - Import/export functionality

2. **Progress Estimation**

   - Estimate time remaining
   - Show download speeds
   - Bandwidth usage

3. **Advanced Syntax Highlighting**

   - Proper shell/bash grammar
   - ANSI color support in logs
   - Syntax error detection

4. **Command History**

   - Save previous commands
   - Quick command insertion
   - Command snippets library

5. **Collaborative Features**
   - Share environment configurations
   - Team templates
   - Installation history

## References

- [Installation Process Logic](./installation-process-logic.md)
- [Syntax Highlighting Implementation](./syntax-highlighting-implementation.md)
- [Environment Management Pseudocode](./environment-management-pseudocode.md)
