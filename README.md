# Resume Keyword Tool

A web app that analyzes job descriptions, finds keyword gaps in your resume, and suggests targeted projects to build — with LaTeX resume generation.

## First-time setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your_key_here
```

## Running the project

```bash
source venv/bin/activate
uvicorn server:app --reload
```

Open **http://localhost:8000** in your browser.

## Stopping the server

Press `Ctrl+C` in the terminal, or from another terminal:

```bash
pkill -f "uvicorn server:app"
```

## Every subsequent run

```bash
# From the project directory
source venv/bin/activate
uvicorn server:app --reload
```
