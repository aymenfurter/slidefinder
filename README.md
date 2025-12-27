<div align="center">

<img src="src/web/static/favicon/favicon.svg" alt="SlideFinder Logo" width="180" height="180">

# SlideFinder

**Search & Build Custom Decks from Microsoft Build & Ignite Presentations**

[![Tests](https://github.com/aymenfurter/slidefinder/actions/workflows/tests.yml/badge.svg)](https://github.com/aymenfurter/slidefinder/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.123-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure](https://img.shields.io/badge/Azure_AI_Search-0078D4?style=flat-square&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com/products/ai-services/ai-search)
[![OpenAI](https://img.shields.io/badge/Azure_OpenAI-412991?style=flat-square&logo=openai&logoColor=white)](https://azure.microsoft.com/products/ai-services/openai-service)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

<br/>


[**Features**](#-features) • [**Quick Start**](#-quick-start) • [**Development**](#development)

<br/>

---

</div>

## ✨ Features

<table>
<tr>
<td width="50%">

### 🔍 **Semantic Slide Search**
- Full-text search across all slide content
- AI-powered agentic retrieval via Azure AI Search
- Filter by event (Build / Ignite)
- Thumbnail previews with direct links

</td>
<td width="50%">

### **AI Deck Builder**
- Natural language deck creation
- Multi-agent architecture (Architect, Critic, Judge)
- Automatic slide selection and curation
- Editable presentation outlines

</td>
</tr>
<tr>
<td width="50%">

### **PPTX Generation**
- Merge selected slides into a single PPTX
- Preserve original formatting and styling
- Download source presentations
- Track slide origins

</td>
<td width="50%">

### ❤️ **Favorites System**
- Save slides for later
- Build collections across searches
- Persistent local storage
- Quick access sidebar

</td>
</tr>
</table>

<br/>

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Azure AI Search service
- Azure OpenAI service (for AI features)

### Installation

```bash
# Clone the repository
git clone https://github.com/aymenfurter/slidefinder.git
cd slidefinder

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Azure credentials
```

### Configuration

Create a `.env` file with your Azure credentials:

```env
# Azure OpenAI
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-search-key
AZURE_SEARCH_INDEX_NAME=slidefinder
```

### Run the Application

```bash
# From project root directory
python -m uvicorn src.main:app --host 0.0.0.0 --port 7004 --reload
```

The app will be available at `http://localhost:7004`

<br/>

## Development

### Project Structure

```
slidefinder/
├── src/                       # Main application code
│   ├── main.py               # FastAPI entry point
│   ├── api/
│   │   └── routes/           # API route handlers
│   │       ├── search.py     # Search endpoints
│   │       ├── slides.py     # Slide info endpoints
│   │       └── deck_builder.py
│   ├── core/                 # Configuration & utilities
│   │   ├── config.py         # Settings (pydantic-settings)
│   │   └── logging.py        # Logging setup
│   ├── models/               # Pydantic data models
│   │   ├── slide.py          # SlideInfo, SlideSearchResult
│   │   └── deck.py           # DeckSession
│   ├── services/
│   │   ├── search/           # Search service
│   │   │   └── azure.py      # Azure AI Search implementation
│   │   ├── pptx/             # PPTX generation
│   │   │   └── merger.py     # Slide merger
│   │   └── deck_builder/     # AI deck builder
│   │       ├── service.py    # Main service
│   │       ├── agents.py     # WorkflowOrchestrator
│   │       ├── workflow.py   # Multi-agent workflow
│   │       ├── prompts.py    # System prompts
│   │       ├── models.py     # Pydantic models
│   │       ├── state.py      # Workflow state
│   │       ├── helpers.py    # Utility functions
│   │       ├── events.py     # SSE event factories
│   │       ├── debug.py      # Debug event emitter
│   │       └── executors/    # Workflow executors
│   │           ├── search.py
│   │           ├── offer.py
│   │           ├── critique.py
│   │           └── judge.py
│   └── web/                  # Frontend assets
│       ├── static/           # CSS, JavaScript
│       └── templates/        # HTML templates
├── indexer/                  # Data indexing pipeline
│   ├── cli.py               # CLI for indexing
│   ├── fetcher.py           # Session data fetcher
│   ├── slide_indexer.py     # PPTX content extraction
│   ├── thumbnails.py        # Thumbnail generation
│   └── ai_search.py         # Azure AI Search upload
├── tests/                    # Test suite
├── scripts/                  # Shell scripts
├── data/                     # Runtime data (ppts, thumbnails, index)
├── infra/                    # Azure Bicep infrastructure
├── Dockerfile
├── requirements.txt
└── azure.yaml               # Azure Developer CLI config
```

### Running Tests

```bash
# Run Python tests
python -m pytest tests/ -v

# Or use the script
./scripts/run_tests.sh

# Run JavaScript tests
cd src/web/static && npm test
```

### Indexing Pipeline

The indexer fetches and processes slides from Microsoft Build & Ignite:

```bash
# Full pipeline
python -m indexer.cli

# Individual steps
python -m indexer.cli --step 1  # Create JSONL index
python -m indexer.cli --step 2  # Generate thumbnails
python -m indexer.cli --step 3  # Upload to Azure AI Search
python -m indexer.cli --step 4  # Verify search
```

### Docker Deployment

```bash
# Build the image
docker build -t slidefinder-app .

# Run the container
docker run -d -p 7004:7004 --env-file .env -v $(pwd)/data:/app/data slidefinder-app
```

### Azure Developer CLI (azd)

```bash
# Deploy to Azure
azd up
```

<br/>

## 🔧 Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | FastAPI, Python 3.11+, Uvicorn |
| **Search** | Azure AI Search (Agentic Retrieval) |
| **AI** | Azure OpenAI (GPT-4.1-mini) |
| **PPTX Processing** | python-pptx |
| **Frontend** | Vanilla JS, CSS3 |
| **Testing** | pytest, Vitest |
| **Deployment** | Docker, Azure Container Apps |

<br/>

## ⚠️ Disclaimer

> **This is a personal project and is NOT affiliated with, endorsed by, or an official product of Microsoft Corporation.**
> 
> All presentation content is the property of Microsoft Corporation. This tool provides search and discovery capabilities for publicly accessible conference materials.

<br/>

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

<br/>
