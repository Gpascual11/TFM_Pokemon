# Python & LaTeX Development Tools Setup

This document explains the setup of the static analysis and type checking tools for the project (configured using `uv`, Ruff, and Ty), as well as the robust LaTeX workflow configured for writing the project report. This standardizes the developer experience and ensures code quality, robust type safety, and a seamless document authoring process.

## What Was Installed?

### 1. **[Ruff](https://docs.astral.sh/ruff/)**
An extremely fast Python linter and code formatter written in Rust (by Astral). It replaces older, slower tools like Flake8, Black, isort, and pyupgrade.
*   **What it does:** Automatically formats code to a consistent style, sorts imports, and detects linting errors (code style issues, unused variables, logic bugs).
*   **Why we use it:** It's lightning fast and consolidates formatting and linting into a single tool.

### 2. **[Ty](https://github.com/astral-sh/ty)**
A next-generation static type checker for Python, also written in Rust by Astral.
*   **What it does:** Analyzes Python code statically (without running it) to ensure that type hints are correct and consistent. It acts as a Language Server in VS Code, meaning it continually scans your code as you type.
*   **Why we use it:** It's a high-performance alternative to Pyright or MyPy, offering faster feedback cycles and advanced type inference, making the codebase more reliable and easier to refactor.

### 3. **[LaTeX Workshop](https://github.com/James-Yu/LaTeX-Workshop) & TexLive**
The premier extension for writing and compiling LaTeX documents in VS Code.
*   **What it does:** Replaces traditional LaTeX editors (like TeXstudio or Overleaf) with a fully integrated VS Code experience, complete with an internal PDF viewer, auto-compilation, and SyncTeX (forward/backward search between code and PDF).
*   **Why we use it:** It unifies the development environment, allowing both Python code and the project's academic report to be authored within the same editor ecosystem.

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
    *   **LaTeX Auto-Build:** We explicitly configured the LaTeX Workshop extension to auto-build on any `.tex` file save (`"latex-workshop.latex.autoBuild.run": "onFileChange"`).
*   **Recommended Extensions (`.vscode/extensions.json`):**
    *   Any developer opening this repository in VS Code will automatically be prompted to install the official Extensions for Ruff (`charliermarsh.ruff`), Ty (`astral-sh.ty`), and LaTeX Workshop (`James-Yu.latex-workshop`).
*   **Git Integrity (`.gitignore`):**
    *   LaTeX compilation produces numerous auxiliary files (`.aux`, `.log`, `.out`, etc.). These are explicitly ignored in our `.gitignore` to keep the project history clean.

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

---

## LaTeX Authoring Workflow

### Automatic Compilation
Because of the `"latex-workshop.latex.autoBuild.run": "onFileChange"` setting:
1. Make a change in any `.tex` file.
2. Press `Ctrl+S` (or `Cmd+S`) to save.
3. The PDF will instantly recompile in the background.

### Viewing the PDF
You can view the compiled report directly inside VS Code!
*   Click the **"View LaTeX PDF"** icon (a page with a magnifying glass) in the top right corner.
*   Or press `Ctrl+Alt+V`.
*   *Tip:* Keep the code on the left and the internal PDF viewer on the right side of your screen for real-time document updates.

### SyncTeX (Navigating the Document)
SyncTeX provides a bridge between the source LaTeX code and the compiled PDF:
*   **Jump from PDF to Code:** Hold `Ctrl` (or `Cmd`) and `Left-Click` on any text inside the PDF viewer. VS Code will instantly jump to the line of `.tex` code that generated that text.
*   **Jump from Code to PDF:** While editing your `.tex` file, press `Ctrl+Alt+J`. The PDF viewer will highlight and scroll directly to the section you are currently editing.
