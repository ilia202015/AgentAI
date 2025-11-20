# AI Agent with Self-Modification Capabilities

🚀 **Advanced AI Agent with real-time code modification and self-improvement capabilities**

## Overview

This is an advanced AI agent built with Python that can modify its own code during runtime. The agent features a sophisticated chat system with tools for Python code execution, sub-chat management, and dynamic self-improvement.

## Key Features

- **🔄 Real-time Self-Modification**: The agent can modify its own code, add new tools, and improve its architecture during execution
- **💬 Multi-Chat System**: Supports creating and managing multiple chat instances with different purposes
- **🐍 Python Code Execution**: Safe execution of Python code with validation and error handling
- **🎯 Adaptive Architecture**: Can create specialized tools and optimize performance based on task requirements
- **📊 Streaming Responses**: Real-time streaming of AI responses for better user experience

## Architecture

### Core Components

- **`Chat` Class**: Main chat handler with tools management and message processing
- **Tool System**: Extensible framework for adding new capabilities
- **Code Validation**: Security-focused Python code validation and execution
- **Streaming API**: Integration with DeepSeek API for real-time responses

### Available Tools

1. **`python`**: Execute Python code safely
2. **`chat`**: Create and manage sub-chats
3. **`chat_exec`**: Execute code within specific chat instances

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd agent
```

2. Install dependencies:
```bash
pip install openai
```

3. Set up API key:
   - Create `api.key` file with your DeepSeek API key

## Usage

Run the agent:
```bash
python agent_med/agent_med.py
```

### Example Interaction

```
🚀 Запуск улучшенного AI-агента с самомодификацией!
============================================================
Агент может:
• Выполнять Python код
• Изменять собственный код во время работы
• Добавлять новые инструменты и функции
• Адаптироваться к новым задачам
============================================================

👤 Вы: [Your message here]
🤖 Агент: [Agent response]
```

## Project Structure

```
agent/
├── agent_med/
│   ├── agent_med.py      # Main agent code
│   ├── system_prompt     # System instructions
│   ├── python_prompt     # Python tool description
│   ├── chat_prompt       # Chat tool description
│   ├── chat_exec_prompt  # Chat execution tool description
│   └── agent_med.log     # Log file
├── api.key              # API key file
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## Configuration

### API Setup

Create `api.key` file in the root directory with your DeepSeek API key:
```
your-deepseek-api-key-here
```

### Environment

- Python 3.7+
- `openai` package
- DeepSeek API access

## Development

The agent is designed to be extensible. You can:

- Add new tools by extending the `tools` list and creating corresponding methods
- Modify the chat behavior by overriding methods
- Create specialized chat instances for different tasks

## Security

- All Python code is validated before execution
- Restricted access to system operations
- Safe execution environment with controlled globals/locals

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license here]

---

**Note**: This agent is designed for educational and research purposes. Use responsibly and ensure proper security measures when executing code.
