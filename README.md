# IWolframEngine: Wolfram Language Kernel for Jupyter

Jupyter provides a protocol (ZMQ) to connect their notebooks to various programming language engines. This project implements a robust, feature-rich Wolfram Language kernel for Jupyter Notebooks and Jupyter Lab.

This repository is a customized version of the Wolfram Language kernel featuring enhanced reliability, auto-completion, and heartbeat support.

---

## Key Features & Improvements

* **Robust Message Parser**: Built on a linear character-scanning state machine. It prevents kernel crashes on unbalanced brackets, nested JSON payloads, or trailing binary buffers.
* **Smart Tab Autocomplete**: Resolves autocompletions for Wolfram Language built-ins, context-specific symbols (e.g., `Developer``), and short Unicode codes (e.g., `\\[Al` matches `α` and `ℵ`).
* **Enhanced Heartbeat Thread**: Restored ZMQ heartbeat loop running on an isolated background sub-kernel. It is hidden from user-visible parallel kernels (e.g., `ParallelKernels[]`) to avoid interference, and includes a single-threaded `SessionSubmit` fallback for resource-constrained environments.
* **Rich MIME Output & Vector SVG Graphics**: Implements native SVG output support for 2D graphics and formulas (cleanly stripped of XML declarations to avoid notebook rendering bugs). Rasterizes high-DPI (144 DPI) PNG fallbacks with proper logical dimensions in metadata to prevent double-sized or blurry images on high-resolution displays, and ensures error messages and output grids are HTML-formatted seamlessly.

---

## Prerequisites

To run this kernel, you need the following installed:

* **Jupyter** or **JupyterLab**
* **Wolfram Engine** (e.g., Wolfram Desktop or Mathematica)
* **wolframscript** (recommended)
* **Python** (for running integration tests, managed via `uv`)

---

## Installation

There are two primary methods to make the Wolfram Language available in Jupyter.

### Method 1: Command Line Installer (Recommended)

1. Clone the repository:
   ```bash
   git clone git@github.com:twn39/IWolframEngine.git
   cd IWolframEngine
   ```
2. Register the kernel spec with Jupyter:
   - **macOS / Linux**:
     ```bash
     ./configure-jupyter.wls add
     ```
   - **Windows**:
     ```powershell
     .\configure-jupyter.wls add
     ```

To specify custom binary paths, use:
```bash
./configure-jupyter.wls help
```

### Method 2: Paclet Installation

1. Build the `.paclet` file locally:
   ```bash
   ./configure-jupyter.wls build
   ```
2. Install the generated paclet in your Wolfram environment:
   ```wolfram
   PacletInstall["WolframLanguageForJupyter-0.9.3.paclet"]
   ```
3. Load the package and register the kernel:
   ```wolfram
   Needs["WolframLanguageForJupyter`"]
   ConfigureJupyter["Add"]
   ```

---

## Testing Your Installation

### 1. Verify Kernel Spec
List registered kernels to check if `wolframlanguage` is found:
```bash
jupyter kernelspec list
```

### 2. Run Diagnostic & Unit Tests
We provide a comprehensive test suite in the `Tests` directory:

- **Message Parser Unit Tests**:
  ```bash
  wolframscript -file Tests/test_actual_parser.wls
  ```
- **Autocomplete Unit Tests**:
  ```bash
  wolframscript -file Tests/test_autocomplete.wls
  ```
- **Heartbeat Thread Unit Tests**:
  ```bash
  wolframscript -file Tests/test_heartbeat.wls
  ```
- **Rich MIME Output Unit Tests**:
  ```bash
  wolframscript -file Tests/test_rich_output.wls
  ```
- **Full Client Integration Tests** (requires `jupyter-client` and `ipykernel` python packages):
  ```bash
  uv run --with jupyter-client --with ipykernel python3 Tests/test_kernel.py
  ```

---

## Removing the Kernel

### Using Command Line
```bash
./configure-jupyter.wls remove
```

### Using Wolfram Language
```wolfram
ConfigureJupyter["Remove"]
```

---

## Links
* **Repository**: [github.com/twn39/IWolframEngine](https://github.com/twn39/IWolframEngine)
* **Jupyter Client Protocol**: [jupyter-client.readthedocs.io](https://jupyter-client.readthedocs.io/en/stable/messaging.html)
