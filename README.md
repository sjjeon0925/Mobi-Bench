## MobiBench Setup

### Install
```bash
git submodule update --init --recursive
cd environment/agent-verifier
pip install -r requirements.txt
```

### API Key Configuration

This project uses different API providers for different components:

- **Model components** (`model/` folder): Uses OpenRouter API
- **AgentBench environment**: Uses OpenAI API

#### Required Environment Variables

You need to set up the following environment variables:

1. `OPENROUTER_API_KEY` - For model components (base_model.py, base_model_GPT5.py)
2. `OPENAI_API_KEY` - For AgentBench environment (agentbench_env.py)

#### Setting Environment Variables

**Option 1: Using .env file (Recommended)**

Create a `.env` file in the project root directory:
```env
# For OpenRouter API (model components)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# For OpenAI API (AgentBench environment)
OPENAI_API_KEY=your_openai_api_key_here
```

**Option 2: System Environment Variables**

**Windows (PowerShell):**
```powershell
$env:OPENROUTER_API_KEY = "your_openrouter_api_key_here"
$env:OPENAI_API_KEY = "your_openai_api_key_here"
```

**Windows (Command Prompt):**
```cmd
set OPENROUTER_API_KEY=your_openrouter_api_key_here
set OPENAI_API_KEY=your_openai_api_key_here
```

**Linux/macOS:**
```bash
export OPENROUTER_API_KEY="your_openrouter_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"
```

**Option 3: Agent Verifier Specific Setup**

For the agent verifier component, create a file named `.env` in the `environment/agent-verifier` directory:
```env
OPENAI_API_KEY=<your_openai_api_key>
```

#### Notes
- The system will automatically detect and use the first available API key from the priority list
- Make sure to replace `your_api_key_here` with your actual API key
- Never commit your actual API keys to version control
- Add `.env` files to your `.gitignore` to prevent accidental commits
