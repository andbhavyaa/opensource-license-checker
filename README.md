# OpenSource License & IP Checker

A fast license compliance tool built with **Portia SDK**. For the love of open source, it helps contributors quickly **scan repositories** and evaluate license compliance, so you can confidently use dependencies in your projects.

## Features

- **Automated license evaluation**: Detects SPDX licenses and flags potential risks
- **Dual interface**: CLI + simple web UI
- **Actionable reports**: JSON, Markdown, and HTML outputs

## Quick Setup

#### Note: make sure to have your API key ready, and to have your Python version 3.12 or above, for Portia requires these two.

## Setup & Running

Create your Virtual Environment (Recommended for Python projects)

### 1. Create a virtual environment

**Linux / macOS:**

```bash
python3 -m venv venv
```

**Windows:**

```bash
python -m venv venv
```

### 2. Activate the virtual environment

**Linux / macOS:**

```bash
source venv/bin/activate
```

**Windows:**

```bash
.\venv\Scripts\Activate.ps1
```

### 3. Install requirements from the requirements.txt

```bash
pip install -r requirements.txt
```

### 4. Run using following commands (either CLI or Web)

#### Example github repo: https://github.com/andbhavyaa/skeldir

### CLI:

```bash
python app.py run --repo https://github.com/andbhavyaa/skeldir
```

### Web:

```bash
uvicorn app:app --reload
```

## Dependencies

(Already taken care of in requirements.txt)

- `bash pip install portia-sdk-python[google]` # Portia SDK with Google API support
- `bash pip install GitPython` # For Git repository handling
- `bash pip install license-expression` # License parsing
- `bash pip install pyyaml` # YAML parsing
- `bash pip install fastapi uvicorn` # Web framework
- `bash pip install jinja2` # Template rendering

### Quick Demo:

<img width="2560" height="1620" alt="license-checker-output" src="https://github.com/user-attachments/assets/2f6107c8-6111-49b1-849f-f57e41141260" />
<img width="2560" height="872" alt="license-checker" src="https://github.com/user-attachments/assets/961867b7-a8c4-4afe-9ce1-e474b857c0be" />
<img width="1919" height="968" alt="image" src="https://github.com/user-attachments/assets/cf282981-36f9-4e03-b66d-bf37ca80d2a6" />

### AI Assistance used:

- Claude AI for basic project structure setup
- Gemini Pro for debugging and license checker function
