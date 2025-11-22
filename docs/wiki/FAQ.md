# Frequently Asked Questions (FAQ)

## General

### What is LeRoPilot?

LeRoPilot is a graphical user interface for LeRobot that simplifies environment management, device configuration, and data recording for robotics projects.

### Is LeRoPilot free?

Yes, LeRoPilot is open source and free to use under the AGPLv3 license. Commercial licensing is also available.

### What platforms are supported?

LeRoPilot supports Windows 10/11, macOS 10.15+, and Linux (Ubuntu 20.04+).

## Installation

### Do I need Python installed?

- **Desktop Mode**: No, Python is bundled with the application
- **Browser Mode**: Yes, Python 3.10 or 3.11 is required

### How much disk space do I need?

- Application: ~200MB
- Each LeRobot environment: 2-5GB (depending on packages)
- Datasets: Varies by recording size

### Can I install multiple versions?

Yes, you can install multiple versions side-by-side. Each version maintains its own configuration.

## Environment Management

### How many environments can I create?

There's no hard limit. Each environment is independent and stored in `~/.leropilot/environments/`.

### Can I use existing Python environments?

Not directly. LeRoPilot creates and manages its own virtual environments to ensure compatibility.

### How do I delete an environment?

Go to Environments → Select environment → Click "Delete". This removes the virtual environment but preserves your data.

### Can I share environments between machines?

Environments are machine-specific due to binary dependencies. However, you can export environment specifications and recreate them on another machine.

## Device Management

### What devices are supported?

LeRoPilot supports devices compatible with LeRobot, including:

- Robot arms (Koch, SO100, etc.)
- Cameras (USB, network cameras)
- Custom devices via configuration

### My camera isn't detected. What should I do?

1. Check if the camera works with other applications
2. Verify USB connection and permissions
3. See [Troubleshooting - Camera Issues](Troubleshooting.md#camera-issues)

### Can I use multiple cameras simultaneously?

Yes, you can configure and use multiple cameras for multi-view recording.

## Data Recording

### Where are datasets stored?

By default, datasets are stored in `~/.leropilot/data/`. You can change this in Settings → Paths → Data Directory.

### What format are recordings saved in?

Recordings are saved in LeRobot's standard format (HDF5 or Parquet, depending on configuration).

### Can I pause and resume recording?

Currently, each recording session creates a separate episode. Pausing/resuming is not yet supported.

## Configuration

### Where is the configuration file?

Configuration is stored in `~/.leropilot/config.json`.

### Can I change the default port?

Yes, in Settings → Server → Port, or via command line:

```bash
leropilot --port 8080
```

### How do I reset to default settings?

Delete `~/.leropilot/config.json` and restart LeRoPilot. A new configuration will be created with defaults.

## Troubleshooting

### The application won't start

1. Check system requirements
2. Review logs in `~/.leropilot/logs/`
3. See [Troubleshooting Guide](Troubleshooting.md)

### Environment creation fails

Common causes:

- Network issues (can't download packages)
- Insufficient disk space
- Python version incompatibility

See [Troubleshooting - Environment Creation](Troubleshooting.md#environment-creation)

### The UI is blank or unresponsive

1. Clear browser cache (browser mode)
2. Restart the application
3. Check if backend is running (look for port 8000)

## Development

### How can I contribute?

See our [Contributing Guide](../CONTRIBUTING.md) for guidelines on submitting pull requests.

### Where can I report bugs?

Report bugs on our [GitHub Issues](https://github.com/fengyj/leropilot/issues) page.

### Is there a development roadmap?

Yes, see our [GitHub Projects](https://github.com/fengyj/leropilot/projects) for planned features.

## Commercial Use

### Can I use LeRoPilot commercially?

Yes, under AGPLv3 (with source code disclosure) or via a commercial license. See [COMMERCIAL.md](../COMMERCIAL.md) for details.

### How do I get a commercial license?

Contact us at fengyj@live.com for commercial licensing inquiries.

## Still Have Questions?

- [GitHub Discussions](https://github.com/fengyj/leropilot/discussions) - Ask the community
- [GitHub Issues](https://github.com/fengyj/leropilot/issues) - Report bugs
- Email: fengyj@live.com
