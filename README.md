# Claude Agents

Claude Agent SDK with Confluence integration.

## Setup

### Prerequisites

- Python 3.10+
- Confluence API token
- Anthropic API key

### Installation

1. Clone the repository and navigate to the project directory.

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

   For development:
   ```bash
   pip install -e ".[dev]"
   ```

4. Copy the environment template and configure credentials:
   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your credentials:
   - `CONFLUENCE_DOMAIN`: Your Atlassian domain (e.g., `your-domain.atlassian.net`)
   - `CONFLUENCE_EMAIL`: Email associated with your Atlassian account
   - `CONFLUENCE_API_TOKEN`: Generate at https://id.atlassian.com/manage-profile/security/api-tokens
   - `ANTHROPIC_API_KEY`: Your Anthropic API key

## Project Structure

```
claude-agents/
├── src/           # Main source code
├── skills/        # Agent skills and tools
├── config/        # Configuration files
├── pyproject.toml # Project dependencies
└── README.md
```

## Usage

See the `src/` and `skills/` directories for implementation details.

## Development

Run tests:
```bash
pytest
```

Lint code:
```bash
ruff check .
```

Type check:
```bash
mypy src/
```
