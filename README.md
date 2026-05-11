# Zel-Plus: Incident Intelligence Engine

![dashboad snapshot](https://github.com/ThatParticularPencil/Zel-Plus/blob/main/Demo%20stuff/Screenshot%202026-05-10%20at%209.06.12%E2%80%AFPM.jpg?raw=true)

An AI-powered incident detection and operational intelligence meant to expand on Zello Transcriptions. It's a prototype to demonstrate how unstructured push-to-talk messages can be parsed into structured incidents to reduce cognitive load and enable automatic task handling.

## System Architecture

The pipeline processes incoming messages through a sequential workflow:

1. **Ingestion**: Real-time message buffering with channel-specific queues
2. **LLM Classification**: Semantic extraction of event type, urgency, topic, and entities
3. **Incident Routing**: Embedding and matching of messages using cosine similarity and heuristics
4. **Incident Store**: Persistent storage of evolving incident states
5. **Task Generation**: Optional automated task suggestions for operational response
6. **Dashboard**: Vibe coded front end for ease of interaction.

## Core Components

- **Message Ingestor** (`engine/message_ingestor.py`): Handles real-time message buffering and channel management
- **Processor** (`engine/processor.py`): LLM-based semantic classification with fallback logic
- **Incident Router** (`engine/incident_router.py`): Weighted scoring system for message-to-incident matching
- **Memory System** (`engine/memory.py`): JSON-based storage for incidents and historical resolution patterns
- **LLM Client** (`services/llm_client.py`): Multi-provider API client (Gemini, Groq, OpenAI, Anthropic)
- **Embedding Client** (`services/embedding_client.py`): Sentence transformer for semantic similarity
- **Schemas** (`models/schemas.py`): Pydantic models for type safety

## Data Model

- **Incident**: Represents an evolving operational issue with ID, channel, status, messages, summary, tasks, and resolution timestamp
- **ProcessedMessage**: LLM-extracted structured data (event_type, urgency, topic, entities) from raw messages
- **MemoryEntry**: Historical incident resolution patterns for retrieval-augmented task generation

## LLM Usage

- **Primary Classification**: Extracts event_type (request/report/update/resolution/noise), urgency (low/medium/high), topic (snake_case operational context), and entities (locations/equipment)
- **Summarization**: Generates concise incident summaries from message threads
- **Task Generation**: Suggests operational actions (dispatch, notify, escalate, log)
- **Fallback Logic**: Rule-based classification when LLM unavailable

## Embeddings & Clustering Strategy

- Topic/entity overlap (45% weight)
- Time proximity (25% weight) 
- Urgency alignment (10% weight)
- Embedding similarity (20% weight, threshold 0.70)

This ensures reliable grouping without over-reliance on semantic similarity, which can be noisy in operational contexts.

## Start

### Prerequisites
- Python 3.9+
- Node.js 18+ (only for frontend)

### Backend Setup
```bash
cd Zel-Plus
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your LLM API keys (GEMINI_API_KEY, GROQ_API_KEY, etc.)
python -m app.main serve
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Access the dashboard at `http://localhost:5173` and API docs at `http://localhost:8000/docs`.

## Example Flow

Consider a warehouse forklift issue:

1. Initial message: `"forklift stuck at dock 2"` → Creates incident #123 with topic `dock_2_forklift_issue`, urgency `high`
2. Update message: `"working on it now"` → Routes to #123, updates summary for new actions
3. Resolution: `"forklift cleared, back in service"` → Routes to #123, marks `resolved`, generates memory entry

The system maintains incident continuity across the conversation thread, enabling dispatch teams to track the issue lifecycle without manual correlation.

I'm currently working on more reliable heuristics and better rules for task making. Obviously, this lacks actual Zello integration, but I can build a simple voice-to-text around it for more functional testing. 
Also, I'm glad to see that this works with pretty weak AI models with little problem.
