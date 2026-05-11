# Zel-Plus: Incident Intelligence Engine

An AI-powered incident detection and operational intelligence system for real-time frontline communication platforms like Zello. This prototype demonstrates how unstructured push-to-talk messages can be transformed into structured operational incidents, reducing cognitive load on dispatch teams and enabling proactive issue detection.

## Problem Statement

Frontline workers in logistics, retail, and manufacturing rely on push-to-talk communication platforms for coordination. These channels generate high-volume, noisy message streams that are difficult to monitor and act upon. Traditional approaches require manual review of every message, leading to missed issues, delayed responses, and inefficient resource allocation. This system addresses the challenge of converting unstructured voice/text streams into actionable operational intelligence.

## System Architecture

The pipeline processes incoming messages through a sequential workflow:

1. **Ingestion**: Real-time message buffering with channel-specific queues
2. **LLM Classification**: Semantic extraction of event type, urgency, topic, and entities
3. **Incident Routing**: Stateful matching of messages to existing incidents using weighted scoring
4. **Incident Store**: Persistent storage of evolving incident states
5. **Task Generation**: Optional automated task suggestions for operational response
6. **Dashboard**: Minimal React frontend for incident monitoring

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

The system supports multiple LLM providers with automatic fallback:

- **Primary Classification**: Extracts event_type (request/report/update/resolution/noise), urgency (low/medium/high), topic (snake_case operational context), and entities (locations/equipment)
- **Summarization**: Generates concise incident summaries from message threads
- **Task Generation**: Suggests operational actions (dispatch, notify, escalate, log)
- **Fallback Logic**: Rule-based classification when LLM unavailable

Providers: Gemini (default), Groq, OpenAI, Anthropic. Configured via `IIE_LLM_PROVIDER` environment variable.

## Embeddings & Clustering Strategy

Embeddings serve as tie-breakers in incident routing, not primary matching signals. The router uses explicit rules first:

- Topic/entity overlap (45% weight)
- Time proximity (25% weight) 
- Urgency alignment (10% weight)
- Embedding similarity (20% weight, threshold 0.70)

This ensures reliable grouping without over-reliance on semantic similarity, which can be noisy in operational contexts.

## How to Run Locally

### Prerequisites
- Python 3.9+
- Node.js 18+ (for frontend)

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
2. Update message: `"working on it now"` → Routes to #123, updates status to `in_progress`
3. Resolution: `"forklift cleared, back in service"` → Routes to #123, marks `resolved`, generates memory entry

The system maintains incident continuity across the conversation thread, enabling dispatch teams to track issue lifecycle without manual correlation.

## Future Improvements

- Enhanced clustering with confidence scoring for uncertain matches
- Evaluation harness for classification accuracy and routing precision  
- Better embedding models for domain-specific semantic understanding
- Real-time alerting integrations for critical incidents
- Historical analytics for operational pattern detection