# Syntax Highlighting Implementation Plan

## Overview

Implement syntax highlighting for command input boxes and terminal output across the application, starting with the environment creation wizard and installation pages.

## Technology Choice: CodeMirror 6

**Selected Library**: `@uiw/react-codemirror` (React wrapper for CodeMirror 6)

**Rationale**:

- Lightweight and performant
- Modular architecture - only load needed features
- Excellent language support (bash, shell, log formats)
- Good React integration
- Smaller bundle size than Monaco Editor
- Highly customizable

## Use Cases

### 1. Command Input Boxes

- **Location**: Advanced Installation Page, future device configuration pages
- **Language**: Bash/Shell (Linux/macOS) or PowerShell/CMD (Windows)
- **Mode**: Editable or Read-only
- **Features**:
  - Syntax highlighting for shell commands
  - Line numbers (optional)
  - Auto-indentation
  - Theme matching (light/dark mode)

### 2. Terminal Output Boxes

- **Location**: Installation logs, command execution output
- **Language**: ANSI log format
- **Mode**: Read-only
- **Features**:
  - Syntax highlighting for log levels (INFO, WARN, ERROR)
  - ANSI color code support
  - Auto-scroll to bottom
  - Theme matching

## Implementation Steps

### Phase 1: Setup Dependencies

```bash
npm install @uiw/react-codemirror
npm install @codemirror/lang-javascript  # For shell/bash
npm install @codemirror/theme-one-dark   # Dark theme
```

### Phase 2: Create Reusable Components

Create two wrapper components:

#### A. `CodeEditor` Component

- Props: `value`, `onChange`, `language`, `readOnly`, `height`
- Features: Syntax highlighting, theme support, line numbers
- Use for: Command input boxes

#### B. `LogViewer` Component

- Props: `logs`, `height`, `autoScroll`
- Features: ANSI color support, auto-scroll, read-only
- Use for: Terminal output

### Phase 3: Integration Points

1. **Advanced Installation Page** (`advanced-installation-page.tsx`)
   - Replace `<textarea>` with `<CodeEditor language="shell" />`
2. **Environment Installation** (`environment-installation.tsx`)

   - Replace command `<textarea>` with `<CodeEditor language="shell" readOnly />`
   - Replace log output with `<LogViewer />`

3. **Future Pages**
   - Device configuration
   - Data recording scripts
   - Custom automation scripts

### Phase 4: Theme Integration

- Detect current app theme (light/dark) from settings
- Apply matching CodeMirror theme
- Support custom color schemes

## Technical Details

### Language Detection

Determine shell language based on:

- User's OS (detected via backend)
- Explicit language setting in advanced mode
- Default: `bash` for Linux/macOS, `powershell` for Windows

### ANSI Color Support

For log viewer:

- Parse ANSI escape codes
- Convert to styled spans
- Support common log formats (timestamp, level, message)

### Performance Considerations

- Lazy load CodeMirror extensions
- Virtual scrolling for large logs
- Debounce onChange events for editable fields

## File Structure

```
frontend/src/components/
├── code-editor/
│   ├── code-editor.tsx       # Editable code input
│   ├── log-viewer.tsx        # Read-only log display
│   └── themes.ts             # Theme configurations
```

## Dependencies

```json
{
  "@uiw/react-codemirror": "^4.21.0",
  "@codemirror/lang-javascript": "^6.2.0",
  "@codemirror/theme-one-dark": "^6.1.0",
  "@codemirror/view": "^6.22.0",
  "@codemirror/state": "^6.3.0"
}
```

## Benefits

1. **Improved UX**: Easier to read and edit commands
2. **Error Prevention**: Visual feedback for syntax errors
3. **Consistency**: Unified code display across the app
4. **Accessibility**: Better contrast and readability
5. **Professionalism**: Modern IDE-like experience

## Future Enhancements

- Code completion for common commands
- Command history navigation
- Snippet support
- Multi-cursor editing
- Search and replace in logs
