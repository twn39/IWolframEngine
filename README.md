# IWolframEngine: Wolfram Language Kernel for Jupyter

This project implements a robust, feature-rich Wolfram Language kernel for Jupyter Notebooks and Jupyter Lab. 

It is built as a hybrid architecture leveraging the official `wolframclient` Python package and `ipykernel`. The Python backend manages ZMQ socket transport, heartbeat, message signing, and lifecycle control, while delegating actual evaluation and rich formatting to a local Wolfram Engine session.

---

## Key Features

* **Zero-Licensing Heartbeat & Concurrency**: Socket transport and heartbeat are handled natively by `ipykernel` in Python. This saves Wolfram license usage and prevents kernel termination during long-running evaluations.
* **Jupyter Status Compliance**: Implements robust error reporting compliant with the Jupyter message specification. Syntax errors, aborts, and uncaught throws return `status: error` with detailed trackbacks and correct `ename`/`evalue` fields, while keeping warning outputs (e.g., `1/0`) non-fatal.
* **Smart Tab Autocomplete**: Supports autocompletions for Wolfram Language built-ins, context-specific symbols (e.g., `Developer``), and short Unicode character names (e.g., `\\[Al` completing to `α`).
* **Rich MIME Output & High-DPI Vector Graphics**: 
  - Produces clean, inline SVG graphics.
  - Automatically rasterizes 144 DPI PNG fallback output with proper logical dimensions inside metadata for crisp rendering on high-resolution Retina displays.
  - Formats syntax errors and warning streams seamlessly.

---

## Prerequisites

1. **Python**: Python 3.8+ (managed via `uv` or `pip`).
2. **Wolfram Engine**: Mathematica, Wolfram Desktop, or free Wolfram Engine installed locally.
3. **wolframscript**: Installed and in your system PATH (for running unit tests).

---

## Installation

We use [uv](https://github.com/astral-sh/uv) to manage Python dependencies and the virtual environment.

### 1. Clone the Repository
```bash
git clone git@github.com:twn39/IWolframEngine.git
cd IWolframEngine
```

### 2. Install the Package and Register the Kernelspec
To install the package in editable mode and register the `wolframlanguage` kernel spec with Jupyter:

```bash
# Install package in editable mode
uv pip install -e .

# Register the Jupyter kernelspec (defaults to current user)
uv run python -m WolframLanguageForJupyter.install
```

To specify a custom prefix or install system-wide, you can run:
```bash
uv run python -m WolframLanguageForJupyter.install --sys-prefix
```

---

## Customizing the Wolfram Kernel Path

By default, the kernel will search for standard installation paths on macOS, Windows, and Linux. If you want to specify a custom Wolfram Kernel binary path, set the `WOLFRAM_KERNEL_PATH` environment variable:

```bash
export WOLFRAM_KERNEL_PATH="/Applications/Wolfram Engine.app/Contents/Resources/Wolfram Player.app/Contents/MacOS/WolframKernel"
```

---

## Running the Tests

We provide tests covering both the Python client integration and Wolfram Language formatting logic.

### 1. Python Integration Tests
Verifies Jupyter client communication, autocomplete behavior, graphics output metadata, and error handling compliance:
```bash
uv run python Tests/test_kernel.py
```

### 2. Wolfram Language Unit Tests
Runs individual tests within the Wolfram environment:
* **Rich MIME Output tests**:
  ```bash
  wolframscript -file Tests/test_rich_output.wls
  ```
* **Autocomplete tests**:
  ```bash
  wolframscript -file Tests/test_autocomplete.wls
  ```

---

## Links
* **Repository**: [github.com/twn39/IWolframEngine](https://github.com/twn39/IWolframEngine)
* **Jupyter Client Protocol**: [jupyter-client.readthedocs.io](https://jupyter-client.readthedocs.io/en/stable/messaging.html)
