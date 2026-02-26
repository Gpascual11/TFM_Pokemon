# Python Development Tools Setup

This document explains the setup of the static analysis and type checking tools for the project, configured using `uv`, Ruff, and Ty. This standardizes the developer experience and ensures code quality, formatting, and robust type safety.

## What Was Installed?

### 1. **[Ruff](https://docs.astral.sh/ruff/)**
An extremely fast Python linter and code formatter written in Rust (by Astral). It replaces older, slower tools like Flake8, Black, isort, and pyupgrade.
*   **What it does:** Automatically formats code to a consistent style, sorts imports, and detects linting errors (code style issues, unused variables, logic bugs).
*   **Why we use it:** It's lightning fast and consolidates formatting and linting into a single tool.

### 2. **[Ty](https://github.com/astral-sh/ty)**
A next-generation static type checker for Python, also written in Rust by Astral.
*   **What it does:** Analyzes Python code statically (without running it) to ensure that type hints are correct and consistent. It acts as a Language Server in VS Code, meaning it continually scans your code as you type.
*   **Why we use it:** It's a high-performance alternative to Pyright or MyPy, offering faster feedback cycles and advanced type inference, making the codebase more reliable and easier to refactor.

---

## How it is Configured

*   **Virtual Environment Management:** Both tools were installed as developer dependencies (`dev`) using `uv`. The binaries live inside the project's centralized `.venv/bin/` folder.
*   **`pyproject.toml`:** 
    *   Ruff's rules are managed here. We have set a maximum line length of `120` characters.
    *   Enabled rule sets include `E` (pycodestyle errors), `F` (Pyflakes), `I` (isort import sorting), `UP` (pyupgrade), and `B` (flake8-bugbear).
    *   We specifically target Python 3.12 syntax.
*   **VS Code Settings (`.vscode/settings.json`):**
    *   **Automated Formatting:** Files are automatically formatted and imports are sorted by Ruff whenever you Save (`Ctrl+S` / `Cmd+S`).
    *   **Language Server Override:** The default Python language server is explicitly disabled so that the Ty language server has full control, avoiding conflicts and redundant analysis.
*   **Recommended Extensions (`.vscode/extensions.json`):**
    *   Any developer opening this repository in VS Code will automatically be prompted to install the official Extensions for Ruff (`charliermarsh.ruff`) and Ty (`astral-sh.ty`).

---

## How to Use It

### Automatic Use (Editor)
If you have the VS Code extensions installed, the tools run automatically:
*   **Linting & Typing:** Real-time squiggly lines will appear under code that violates type definitions or Ruff linting rules. Hovering over them provides detailed error messages.
*   **Formatting:** Simply save the file, and Ruff will automatically correct formatting issues and organize your imports.

### Manual Use (Command Line)
You can directly run the tools inside the virtual environment using `uv`:

**Formatting Code**
```bash
# Format all code in the project
uv run ruff format .
```

**Linting Code**
```bash
# Check for lint issues without fixing them automatically
uv run ruff check .

# Check and automatically fix safe lint issues
uv run ruff check --fix .
```

**Type Checking**
```bash
# Run a full static type check across the project
uv run ty check
```
