# Quick Start

This guide will help you get started with LeRoPilot in 5 minutes.

## Prerequisites

- LeRoPilot installed ([Installation Guide](Installation-Guide.md))
- Internet connection (for downloading LeRobot packages)

## Step 1: Launch LeRoPilot

**Desktop Mode**: Launch the application from your applications menu or desktop shortcut.

**Browser Mode**:

```bash
python -m leropilot.main
```

Then open `http://localhost:8000` in your browser.

## Step 2: Create Your First Environment

1. Click **"Environments"** in the sidebar
2. Click **"Create New Environment"**
3. Follow the wizard:
   - **Name**: Enter a name (e.g., "my-first-env")
   - **LeRobot Version**: Select a version (latest recommended)
   - **PyTorch Version**: Select a compatible version
   - **Python Version**: 3.10 or 3.11
4. Click **"Create"**

The environment creation process will:

- Create a Python virtual environment
- Install LeRobot and dependencies
- Configure the environment

This may take 5-10 minutes depending on your internet speed.

## Step 3: Activate the Environment

Once created, you can:

- **View Details**: Click on the environment card
- **Activate**: Use the activation command shown in the UI
- **Open Terminal**: Launch a terminal with the environment activated

## Step 4: Configure Devices (Optional)

1. Go to **"Devices"** in the sidebar
2. Click **"Add Device"**
3. Select device type:
   - **Robot**: Configure your robot arm
   - **Camera**: Add cameras for recording
4. Follow the device-specific setup wizard

## Step 5: Start Recording (Optional)

1. Navigate to **"Recording"**
2. Select your environment and devices
3. Click **"Start Recording"**
4. Perform your demonstration
5. Click **"Stop"** when done

Your dataset will be saved in the configured data directory.

## Next Steps

- [Environment Management](Environment-Management.md) - Learn more about managing environments
- [Device Management](Device-Management.md) - Configure robots and cameras
- [Data Recording](Data-Recording.md) - Advanced recording features
- [Configuration](Configuration.md) - Customize LeRoPilot settings

## Need Help?

- [FAQ](FAQ.md) - Common questions
- [Troubleshooting](Troubleshooting.md) - Common issues
- [GitHub Issues](https://github.com/fengyj/leropilot/issues) - Report bugs
