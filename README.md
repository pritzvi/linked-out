# LinkedOut

[![PyPI](https://img.shields.io/pypi/v/mimicflow.svg)](https://pypi.org/project/mimicflow/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/pritzvi/mimicflow/blob/main/LICENSE)

Automate your LinkedIn networking using an intelligent browser agent. Upload your resume, craft example messages, and let the agent handle the networking while you focus on what matters.

## Features

- **Resume-Based Networking**: Upload your resume and let the agent craft personalized connection messages
- **Flexible Search**: Find potential connections using LinkedIn search URLs or custom filters
- **Multiple Modes**: 
  - Full automation: Connect with personalized messages
  - Lite mode: Connect without messages
  - Observer mode: Just collect profile information without connecting

## Project Structure

- `frontend/`: React-based UI code (TypeScript)
- `mimicflow/agents/`: LinkedIn automation agent code
- `mimicflow/app/`: FastAPI backend
- `browser-use/`: Browser automation framework powered by [browser-use](https://browser-use.com/), using LangChain and Playwright. We've modified it for our LinkedIn use case.

## Setup Instructions

1. Install uv (choose one method):
```bash
# Using curl (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Using pip
pipx install uv

# Using Homebrew
brew install uv
```

2. Create and activate virtual environment:
```bash
uv venv --python 3.11
source .venv/bin/activate
```

3. Install dependencies:
```bash
uv sync
uv pip install -e ./browser-use
uv pip install playwright
playwright install
```

4. Set up frontend:
```bash
cd frontend
npm install
npm run dev
```

If you encounter frontend setup issues:
```bash
rm -rf node_modules
rm package-lock.json
npm install
npm run dev
```

5. Start the backend (from root directory):
```bash
uv run uvicorn mimicflow.app.main:app --reload --host 0.0.0.0 --port 8000
```

6. Set environment variables:
```bash
export OPENAI_API_KEY=your_key_here
export GEMINI_API_KEY=your_key_here
```

## Usage

1. Make sure you're logged into LinkedIn on Chrome
2. Completely quit Chrome browser (ensure it's not running in background)
3. Open `localhost:5173` in a different browser (e.g., Safari)
4. Configure your automation parameters:
   - Upload your resume
   - Set your API keys
   - Choose connection mode
   - Enter LinkedIn search URL or filters
   - Start automation

The frontend runs on port 5173 and the backend on port 8000.

## Development

To contribute to this project:
1. Fork the repository
2. Create a new branch for your feature
3. Submit a pull request

## License

Apache 2.0
