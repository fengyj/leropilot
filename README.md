# LeRoPilot

**License:** AGPLv3 — Copyright © 2025 冯裕坚 (Feng Yu Jian) <fengyj@live.com>. Personal use is free; commercial licenses available (see `COMMERCIAL.md`).

中文说明：参见 `README_zh.md`。

LeRoPilot is a local development environment manager packaged as a single executable file. It provides a web-based interface to manage Python development environments.

## Installation

### Prerequisites

- **For building from source only**: Python 3.10+, Node.js 16+
- **For running the executable**: No dependencies required

### Download and Run

Download the pre-built executable for your platform from the releases page:

#### Windows

1. Download `leropilot.exe`
2. Double-click `leropilot.exe` to start the application
3. The application will automatically open in your default browser at `http://127.0.0.1:8000`

#### macOS

1. Download `leropilot`
2. Open Terminal and navigate to the download location
3. Make the file executable:
   ```bash
   chmod +x leropilot
   ```
4. Run the application:
   ```bash
   ./leropilot
   ```
5. The application will automatically open in your default browser at `http://127.0.0.1:8000`

#### Linux

1. Download `leropilot`
2. Open Terminal and navigate to the download location
3. Make the file executable:
   ```bash
   chmod +x leropilot
   ```
4. Run the application:
   ```bash
   ./leropilot
   ```
5. The application will automatically open in your default browser at `http://127.0.0.1:8000`

## Building from Source

If you want to build the executable yourself:

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Build

```bash
python scripts/build.py
```

The executable will be generated in the `dist/` directory.

### 3. Verify Build Size (Optional)

```bash
python scripts/ci_size_check.py
```

## Development

### Running in Development Mode

**Backend:**
```bash
python -m leropilot.main
```

**Frontend:**
```bash
cd frontend
npm run dev
```

The development server will be available at `http://localhost:5173` with API proxy to the backend.

## Configuration

The application stores its data in `~/.leropilot/`:
- Configuration file: `~/.leropilot/config.yaml`
- Logs: `~/.leropilot/logs/`

You can customize settings by creating a `config.yaml` file:

```yaml
port: 8000
data_dir: ~/.leropilot
```

Environment variables can also be used with the `LEROPILOT_` prefix:
```bash
export LEROPILOT_PORT=9000
```

## License

See LICENSE file for details.
