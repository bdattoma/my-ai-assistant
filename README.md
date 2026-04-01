# LangGraph Code Assistant

A conversational AI code assistant built with LangGraph that features file operations, approval mechanisms, streaming responses, and a skills system.

## Features

- 🤖 **LLM-Powered Agent** - Uses OpenAI-compatible APIs with streaming responses
- 📁 **File Operations** - Read, write, and list files with approval prompts
- 🎯 **Skills System** - Load specialized knowledge on-demand (database, API, greetings, etc.)
- ✅ **Approval Mechanism** - Human-in-the-loop for sensitive operations like file writes
- 💬 **Session Management** - Maintain conversation context across interactions
- ⚡ **Token Streaming** - Real-time response streaming for better UX

## Disclaimer

> **Note:** Most of the code in this project was developed with assistance from [Claude Code](https://claude.ai/claude-code), Anthropic's AI-powered coding assistant. This project serves as a demonstration of AI-assisted development and LangGraph capabilities.

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer

## Installation

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install Dependencies

```bash
# Install dependencies using uv
uv pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in the project root or copy from the example:

```bash
cp .env.example .env
```

Edit `.env` with your LLM server details:

```bash
# OpenAI-compatible LLM server configuration
OPENAI_BASE_URL=https://your-llm-server.com/v1
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=your-model-name
```

## Usage

### Running the Server

Start the FastAPI server with approval support:

```bash
uv run python llm_api_server.py
```

The server will start on `http://localhost:8000`

**API Endpoints:**
- `GET /` - Health check
- `POST /chat/stream` - Chat with streaming (SSE)
- `POST /approve` - Approve/reject pending tool calls
- `GET /session/{id}` - Get conversation history
- `DELETE /session/{id}` - Delete session
- `GET /sessions` - List all sessions

### Running the CLI

In a separate terminal, start the interactive CLI client:

```bash
uv run python llm_assistant_cli.py
```

**CLI Commands:**
- `/exit` or `/quit` - Exit the chat
- `/reset` - Start a new conversation
- `/history` - Show conversation history
- `/help` - Show help message

### Example Interactions

```
💬 You: Create a Python file that prints hello world

🤖 AI: I'll create a simple Python file for you.

⚠️  APPROVAL REQUIRED ⚠️
   Tool: write_file
   Arguments:
     file_path: hello.py
     content: (Content is 24 characters, 1 lines)

--- File Content Preview (first 500 chars) ---
print("Hello, World!")
--- End Preview ---

   Approve this action? [y/n/v for full view]: y

   ▶ Executing write_file...
   ✓ Result: Successfully wrote 24 characters to hello.py

🤖 AI: I've created hello.py with a simple hello world program.
```

## Skills System

Skills are markdown files in the `skills/` directory that provide specialized instructions to the agent.

### Available Skills

- `AGENT.md` - Base agent skills (always loaded)
- `GREETINGS.skill.md` - Custom greeting responses
- Add your own: `DATABASE.skill.md`, `API.skill.md`, etc.

### Creating Custom Skills

Create a new `.skill.md` file in the `skills/` directory:

```bash
# skills/CUSTOM.skill.md
# Your Custom Skill

## Instructions
- Specific guidelines for the agent
- Best practices
- Examples
```

The agent will automatically discover and load relevant skills based on the conversation context.

## Project Structure

```
hello-agent/
├── llm_agent.py                           # Main agent logic
├── llm_api_server.py                      # FastAPI server with approval
├── code_assistant_cli_with_approval.py    # CLI client
├── tools.py                               # Tool definitions
├── skills.py                              # Skills management system
├── requirements.txt                       # Python dependencies
├── .env                                   # Environment configuration
├── skills/                                # Skills directory
│   ├── AGENT.md                          # Base skills (always loaded)
│   └── GREETINGS.skill.md                # Custom greetings
└── README.md                             # This file
```

## Tools Available

The agent has access to these tools:

- `write_file` - Create/overwrite files (requires approval)
- `read_file` - Read file contents
- `list_files` - List directory contents
- `list_skills` - List available skill files
- `load_skill` - Load a specific skill file

## Development

### Adding New Tools

1. Add a new function in `tools.py` with the `@tool` decorator
2. Add the tool name in `all_tools` list variable in `tools/tools.py`
3. Add to `APPROVAL_REQUIRED_TOOLS` if it needs user approval. Otherwise it will run without asking for approval

```python
@tool
def your_new_tool(param: str) -> str:
    """Tool description"""
    # Implementation
    return result
```

### Customizing the Agent

Edit `skills/AGENT.md` to modify the agent's base behavior, coding standards, and guidelines.

## Troubleshooting

### Server won't start
- Check if port 8000 is available
- Verify `.env` configuration is correct
- Ensure all dependencies are installed

### Model not responding
- Verify `OPENAI_BASE_URL` is correct and accessible
- Check `OPENAI_API_KEY` is valid
- Confirm `OPENAI_MODEL` name matches your server

### Streaming not working
- Ensure you're using `llm_api_server.py` (not other variants)
- Check browser/client supports Server-Sent Events (SSE)

## License

MIT

## Contributing

Contributions welcome! Feel free to open issues or submit pull requests.
