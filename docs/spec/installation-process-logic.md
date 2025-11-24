# Installation Process Logic

This document outlines the logic for the environment installation process, including handling cancellations, retries, and navigation.

## 1. Installation States

The installation process can be in one of the following states:

- **Pending**: Installation has not started yet.
- **Running**: Installation is currently in progress.
- **Success**: All steps completed successfully.
- **Error**: One or more steps failed.
- **Cancelled**: User manually cancelled the installation.

## 2. Cancellation Logic

- **Trigger**: User clicks the "Cancel" (取消) button during the **Running** state.
- **Confirmation**: A confirmation dialog (`window.confirm`) appears asking "Are you sure you want to cancel? This may leave the environment in an inconsistent state."
- **Action**:
  - If confirmed, the installation process stops immediately.
  - The currently running step is marked as **Error** (or Cancelled) in the UI.
  - A log entry "Installation cancelled by user." is added to the current step.
  - The global state is set to `isCancelled = true`.

## 3. Post-Cancellation / Failure Actions

When the installation stops due to an error or cancellation, the available actions change:

### A. Retry (重试)

- **Condition**: Visible when the installation failed due to an error (but was NOT cancelled by the user).
- **Behavior**:
  - Resumes installation from the **first failed step**.
  - Resets the status of the failed step and all subsequent steps to `pending`.
  - Clears logs for the failed step and subsequent steps.
  - Starts execution from the failed step.

### B. Reinstall (重新安装)

- **Condition**: Visible when the installation was **Cancelled** by the user.
- **Behavior**:
  - Performs a full cleanup of the environment (simulated in frontend, backend needs to implement actual cleanup).
  - Resets **ALL** steps to `pending`.
  - Clears logs for all steps.
  - Starts execution from **Step 1** (beginning).

### C. Back (上一步)

- **Condition**: Visible when the installation is **Cancelled**.
- **Behavior**:
  - Triggers a cleanup operation (to ensure no partial files are left).
  - Navigates back to the previous page (either the **Wizard** or **Advanced Installation** page).
  - Allows the user to modify configuration before trying again.

## 4. Navigation Logic

- **Wizard Navigation**:
  - The Wizard steps are synced with the URL query parameter `?step=N`.
  - Clicking the browser's "Back" button navigates to the previous wizard step, preserving the user's context.
- **Advanced Mode**:
  - Clicking "Create" in Advanced Mode saves the custom steps to the store and navigates to the Installation page.
- **Installation Page**:
  - Does not have a "Back" button while running (to prevent accidental interruption).
  - "Cancel" button is the primary way to stop the process.

## 5. Backend Implications

- **Cancellation Endpoint**: The backend needs to support a cancellation signal that can terminate the running process immediately.
- **Cleanup Logic**:
  - On **Reinstall** or **Back** (after partial install), the backend should be able to clean up the partially created environment (e.g., delete the `.venv` directory, remove the cloned repo).
- **Idempotency**:
  - Ideally, installation steps should be idempotent.
  - **Retry** relies on the ability to re-run a step that might have partially failed.
  - **Reinstall** relies on the ability to wipe the slate clean and start over.
