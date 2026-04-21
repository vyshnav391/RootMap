# RootMap

**AI-powered personalised learning gap detector for students aged 12–18.**

RootMap is a full-stack, microservices-based educational platform that identifies knowledge gaps, adapts question selection in real time, and generates personalised study plans using a combination of Bayesian Knowledge Tracing, graph-based prerequisite modelling, and large language model reasoning.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Services](#services)
  - [BKT Engine](#bkt-engine)
  - [Question Selector](#question-selector)
  - [LLM Study Planner](#llm-study-planner)
- [Knowledge Graph](#knowledge-graph)
- [RAG Pipeline](#rag-pipeline)
- [Infrastructure](#infrastructure)
- [CI/CD Pipeline](#cicd-pipeline)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Running Locally with Docker](#running-locally-with-docker)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Students frequently progress through curricula with undetected conceptual gaps that compound over time. RootMap addresses this by continuously modelling each student's mastery state across topics, selecting questions that maximise diagnostic value, and producing actionable, personalised study plans.

The system is designed as a decoupled microservices architecture. Each AI service operates independently, communicates over REST, and can be scaled, updated, or replaced without affecting the rest of the platform. The frontend is a React single-page application; the backend is built on FastAPI with a Neo4j knowledge graph and PostgreSQL for persistent student data.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend                        │
│                    (Cloud Run — Static)                      │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼─────────────────────────────────┐
│                      API Gateway                             │
│                  FastAPI — Core Service                      │
│                   (Cloud Run — GCP)                          │
└──────┬──────────────────┬─────────────────────┬─────────────┘
       │                  │                     │
┌──────▼──────┐  ┌────────▼────────┐  ┌────────▼────────────┐
│  BKT Engine │  │ Question        │  │ LLM Study Planner   │
│  Service    │  │ Selector        │  │ Service             │
│ (Cloud Run) │  │ (Cloud Run)     │  │ (Cloud Run)         │
└──────┬──────┘  └────────┬────────┘  └────────┬────────────┘
       │                  │                     │
┌──────▼──────────────────▼──────┐   ┌─────────▼────────────┐
│         PostgreSQL              │   │      Neo4j           │
│   (Student mastery records)     │   │  (Knowledge Graph)   │
└─────────────────────────────────┘   └──────────────────────┘
```

All services are containerised via Docker and deployed to Google Cloud Run. Inter-service communication uses authenticated internal HTTP. The CI/CD pipeline on GitHub Actions handles build, test, and deployment on every push to `main`.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, TanStack Query |
| API Gateway | FastAPI, Python 3.11, Pydantic v2 |
| BKT Engine | Python, NumPy, custom HMM implementation |
| Question Selector | Python, scikit-learn, uncertainty sampling |
| LLM Study Planner | Claude API (claude-sonnet), LangChain |
| Knowledge Graph | Neo4j 5, Cypher |
| Relational DB | PostgreSQL 15, SQLAlchemy, Alembic |
| Containerisation | Docker, Docker Compose |
| Cloud | GCP Cloud Run, Artifact Registry, Cloud SQL |
| CI/CD | GitHub Actions |
| Observability | GCP Cloud Logging, Cloud Monitoring |

---

## Services

### BKT Engine

The BKT (Bayesian Knowledge Tracing) Engine models each student's latent knowledge state as a Hidden Markov Model over a binary mastery variable per topic.

**Parameters per topic:**

| Parameter | Symbol | Description |
|---|---|---|
| Prior mastery | P(L0) | Probability student already knows topic at start |
| Learning rate | P(T) | Probability of transitioning from unknown to known after practice |
| Slip | P(S) | Probability of answering incorrectly despite knowing |
| Guess | P(G) | Probability of answering correctly without knowing |

After each student response, the engine updates the posterior mastery probability using Bayes' theorem. The updated state is persisted and fed back to the Question Selector and Study Planner.

**Endpoint:** `POST /bkt/update`

**Input:**
```json
{
  "student_id": "string",
  "topic_id": "string",
  "correct": true
}
```

**Output:**
```json
{
  "topic_id": "string",
  "p_mastery": 0.74,
  "updated_at": "2025-06-01T10:23:00Z"
}
```

---

### Question Selector

The Question Selector uses **uncertainty sampling** to choose the question most likely to reduce uncertainty about the student's mastery state. Given a student's current mastery probability vector, it selects the topic closest to the decision boundary (P(mastery) = 0.5) and retrieves a question of appropriate difficulty.

The selector also respects the prerequisite ordering encoded in the Neo4j knowledge graph — it will not surface questions on a topic whose prerequisites have not reached a minimum mastery threshold.

**Endpoint:** `POST /selector/next`

**Input:**
```json
{
  "student_id": "string",
  "session_id": "string"
}
```

**Output:**
```json
{
  "question_id": "string",
  "topic_id": "string",
  "difficulty": 2,
  "content": "string",
  "options": ["string"]
}
```

---

### LLM Study Planner

The LLM Study Planner generates a structured, personalised study plan by combining:

1. The student's current mastery state vector (retrieved from the BKT Engine)
2. The prerequisite dependency graph (retrieved from Neo4j)
3. Curated topic summaries and learning objectives (retrieved via RAG pipeline)

A prompt is constructed and sent to the Claude API. The model returns a step-by-step study plan with prioritised topics, recommended resources, and suggested daily time allocations. The response is parsed, validated against a Pydantic schema, and returned to the frontend.

**Endpoint:** `POST /planner/generate`

**Input:**
```json
{
  "student_id": "string",
  "target_topic_id": "string",
  "available_hours_per_week": 5
}
```

**Output:**
```json
{
  "plan_id": "string",
  "weeks": [
    {
      "week": 1,
      "focus_topics": ["string"],
      "daily_tasks": ["string"],
      "estimated_hours": 5
    }
  ],
  "generated_at": "2025-06-01T10:23:00Z"
}
```

---

## Knowledge Graph

The prerequisite knowledge graph is modelled in Neo4j. Topics are nodes; directed edges represent prerequisite relationships.

**Node: Topic**
```
(t:Topic {
  id: "algebra_linear_equations",
  name: "Linear Equations",
  subject: "Mathematics",
  difficulty: 2,
  grade_band: "7-9"
})
```

**Relationship: REQUIRES**
```
(t1:Topic)-[:REQUIRES]->(t2:Topic)
```

This models, for example, that understanding quadratic equations requires prior mastery of linear equations. The Question Selector traverses this graph to enforce prerequisite ordering. The Study Planner uses topological ordering of the subgraph to sequence topics in a study plan.

**Sample Cypher — find all unmastered prerequisites for a student:**
```cypher
MATCH (target:Topic {id: $target_id})<-[:REQUIRES*]-(prereq:Topic)
WHERE NOT EXISTS {
  MATCH (s:Student {id: $student_id})-[m:MASTERED]->(prereq)
  WHERE m.p_mastery >= 0.8
}
RETURN prereq
ORDER BY prereq.difficulty ASC
```

---

## RAG Pipeline

The RAG (Retrieval-Augmented Generation) pipeline supports the LLM Study Planner. Topic summaries, learning objectives, and common misconceptions are stored as documents in a vector store. At planning time, the planner embeds the student's gap profile, retrieves the most relevant topic documents, and injects them into the Claude API prompt as context.

**Pipeline steps:**

1. **Ingestion** — Topic documents are embedded using `text-embedding-3-small` and stored in a vector index.
2. **Retrieval** — At inference time, the student's mastery gap vector is used to construct a query; top-k documents are retrieved.
3. **Augmentation** — Retrieved documents are injected into the system prompt alongside the mastery state.
4. **Generation** — Claude generates the study plan grounded in the retrieved context.
5. **Validation** — The response is parsed against a Pydantic schema; malformed outputs trigger a retry with corrective instructions.

---

## Infrastructure

All services are deployed to **GCP Cloud Run** as independent, stateless containers. Each service auto-scales to zero when idle and scales horizontally under load.

| Service | Cloud Run Instance | Min Instances | Max Instances |
|---|---|---|---|
| Core API | `rootmap-api` | 0 | 10 |
| BKT Engine | `rootmap-bkt` | 0 | 5 |
| Question Selector | `rootmap-selector` | 0 | 5 |
| LLM Study Planner | `rootmap-planner` | 0 | 3 |

Container images are stored in **GCP Artifact Registry**. The PostgreSQL database runs on **Cloud SQL (PostgreSQL 15)**. Neo4j runs as a managed instance on **Neo4j Aura**.

---

## CI/CD Pipeline

The GitHub Actions pipeline runs on every push to `main` and on all pull requests.

```
Push to main
    │
    ├── Lint & Type Check (ruff, mypy, eslint)
    │
    ├── Unit Tests (pytest, vitest)
    │
    ├── Integration Tests (Docker Compose test environment)
    │
    ├── Build Docker Images
    │       └── Push to GCP Artifact Registry
    │
    └── Deploy to Cloud Run
            ├── rootmap-api
            ├── rootmap-bkt
            ├── rootmap-selector
            └── rootmap-planner
```

Pull requests trigger lint, type check, and unit test steps only. Deployment is gated on all checks passing.

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 20+
- A Neo4j Aura account (or local Neo4j instance)
- A GCP project with Cloud Run and Cloud SQL enabled (for cloud deployment)
- An Anthropic API key

### Environment Variables

Copy `.env.example` to `.env` and fill in the required values.

```bash
cp .env.example .env
```

**`.env.example`:**
```env
# Core API
DATABASE_URL=postgresql://user:password@localhost:5432/rootmap
SECRET_KEY=your-secret-key

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-neo4j-password

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key

# Internal service URLs (override for local dev)
BKT_SERVICE_URL=http://localhost:8001
SELECTOR_SERVICE_URL=http://localhost:8002
PLANNER_SERVICE_URL=http://localhost:8003

# GCP (for cloud deployment)
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
```

### Running Locally with Docker

```bash
# Clone the repository
git clone https://github.com/your-org/rootmap.git
cd rootmap

# Start all services
docker compose up --build

# Apply database migrations
docker compose exec api alembic upgrade head

# Seed the knowledge graph
docker compose exec api python scripts/seed_knowledge_graph.py
```

The React frontend will be available at `http://localhost:3000`.
The Core API will be available at `http://localhost:8000`.
API documentation (Swagger UI) will be available at `http://localhost:8000/docs`.

---

## API Reference

Full OpenAPI documentation is generated automatically by FastAPI and available at `/docs` when the server is running.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new student account |
| `POST` | `/auth/login` | Authenticate and receive a JWT |
| `GET` | `/students/{id}/mastery` | Retrieve full mastery state for a student |
| `POST` | `/sessions/start` | Start a new practice session |
| `POST` | `/sessions/{id}/answer` | Submit an answer; triggers BKT update |
| `GET` | `/sessions/{id}/next` | Get the next question for a session |
| `POST` | `/planner/generate` | Generate a personalised study plan |
| `GET` | `/topics` | List all topics in the knowledge graph |
| `GET` | `/topics/{id}/prerequisites` | Get prerequisite topics for a given topic |

---

## Project Structure

```
rootmap/
├── frontend/                   # React + TypeScript SPA
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── api/                # TanStack Query hooks
│   │   └── types/
│   ├── Dockerfile
│   └── vite.config.ts
│
├── services/
│   ├── api/                    # Core FastAPI gateway
│   │   ├── routers/
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── db/                 # Database session and migrations
│   │   ├── main.py
│   │   └── Dockerfile
│   │
│   ├── bkt/                    # BKT Engine service
│   │   ├── engine.py           # HMM implementation
│   │   ├── router.py
│   │   ├── main.py
│   │   └── Dockerfile
│   │
│   ├── selector/               # Question Selector service
│   │   ├── selector.py         # Uncertainty sampling logic
│   │   ├── graph_client.py     # Neo4j query layer
│   │   ├── router.py
│   │   ├── main.py
│   │   └── Dockerfile
│   │
│   └── planner/                # LLM Study Planner service
│       ├── planner.py          # RAG pipeline + Claude integration
│       ├── vector_store.py     # Embedding and retrieval
│       ├── prompt_builder.py
│       ├── router.py
│       ├── main.py
│       └── Dockerfile
│
├── scripts/
│   ├── seed_knowledge_graph.py
│   └── seed_questions.py
│
├── infra/                      # GCP and Docker config
│   └── cloud-run/
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml
│
├── docker-compose.yml
├── docker-compose.test.yml
└── .env.example
```

---

## Development

### Backend

```bash
cd services/api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Repeat for `bkt`, `selector`, and `planner` services on ports 8001, 8002, and 8003.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Code Quality

```bash
# Python — lint and type check
ruff check .
mypy .

# Python — format
ruff format .

# Frontend — lint
npm run lint

# Frontend — type check
npm run type-check
```

---

## Testing

### Unit Tests

```bash
# Backend
pytest services/ -v

# Frontend
cd frontend && npm run test
```

### Integration Tests

Integration tests spin up a full Docker Compose environment and test service interactions end-to-end.

```bash
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

---

## Deployment

Deployment is handled automatically by the GitHub Actions CI/CD pipeline on merge to `main`. To deploy manually:

```bash
# Authenticate with GCP
gcloud auth login
gcloud config set project $GCP_PROJECT_ID

# Build and push images
docker build -t gcr.io/$GCP_PROJECT_ID/rootmap-api ./services/api
docker push gcr.io/$GCP_PROJECT_ID/rootmap-api

# Deploy to Cloud Run
gcloud run deploy rootmap-api \
  --image gcr.io/$GCP_PROJECT_ID/rootmap-api \
  --region $GCP_REGION \
  --allow-unauthenticated
```
