<div align="center">
  <img src="https://ui-avatars.com/api/?name=AEGIS&background=1e293b&color=ef4444&size=128" alt="AEGIS Logo" width="128" height="128" style="border-radius: 20%;">
  <h1>AEGIS AI — Automated Enforcement & Guardian Intelligence System</h1>
  <p><strong>A Real-Time WhatsApp Moderation Platform to Protect Children from Online Harassment</strong></p>
  
  [![Angular](https://img.shields.io/badge/Angular-21+-red.svg)](https://angular.io/)
  [![Django](https://img.shields.io/badge/Django-5.2+-green.svg)](https://www.djangoproject.com/)
  [![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
  [![PyTorch](https://img.shields.io/badge/PyTorch-2.11+-ee4c2c.svg)](https://pytorch.org/)
</div>

<hr>

**AEGIS** is an intelligent, real-time cyberbullying prevention platform built as a *Projet de Fin d'Études (PFE)*. It actively intercepts, analyzes, and moderates WhatsApp conversations, providing automated enforcement (Active Shield) and comprehensive parental monitoring.

Designed with a robust **5-Agent AI Architecture**, AEGIS supports **French**, **Arabic**, and **Darija (Moroccan Arabic)** to address specific regional moderation challenges.

---

## 🏗️ System Architecture

AEGIS employs an asynchronous pipeline where specialized AI agents cooperate to deliver rapid, accurate moderation:

```mermaid
graph TD
    %% Define Styles
    classDef wp fill:#25D366,stroke:#fff,color:#fff,font-weight:bold;
    classDef django fill:#092E20,stroke:#44B78B,color:#fff,font-weight:bold;
    classDef agent fill:#1E293B,stroke:#6366F1,color:#fff,stroke-width:2px;
    classDef action fill:#ef4444,stroke:#fff,color:#fff,font-weight:bold;
    
    %% Nodes
    WA((WhatsApp Node)):::wp
    Evo[Evolution API <br/> Webhook Event]:::wp
    
    subgraph AEGIS Backend [AEGIS Django Backend & ML Pipeline]
        Router[Webhook Router]:::django
        
        A1[Agent 1: Gatekeeper <br/> Binary Toxicity]:::agent
        A2[Agent 2: Specialist <br/> 6-Class Categorization]:::agent
        A3[Agent 3: Auditor <br/> Groq LLM Grey Zone]:::agent
        A4[Agent 4: Profiler <br/> User Risk Scoring]:::agent
        A5[Agent 5: Orchestrator <br/> Policy Enforcer]:::agent
        
        Router --> A1
        A1 -- "Suspicious" --> A2
        A2 -- "Low Confidence / Semantic" --> A3
        A1 -- "Safe / High Confidence" --> A4
        A3 --> A4
        A4 --> A5
    end
    
    subgraph Outcomes [Real-Time Enforcement]
        UI[Angular Dashboard <br/> Parent/Admin UI]:::django
        ActDel[Active Shield <br/> (Delete Message)]:::action
        ActWarn[Auto-Reply <br/> (Warn Sender)]:::action
    end
    
    %% Flow
    WA --> Evo
    Evo --> Router
    A5 -.-> ActDel
    A5 -.-> ActWarn
    A5 -.-> UI
```

---

## 🧠 Multi-Agent AI Pipeline

1. **Agent 1 (Gatekeeper)**: An optimized BERT model that scans incoming text for general toxicity. Fast and lightweight ($<50$ms).
2. **Agent 2 (Specialist)**: A secondary NLP model that categorizes harmful content into 6 distinct specific classes (e.g., *Sexual Harassment*, *Threats*).
3. **Agent 3 (Auditor)**: A Large Language Model (Groq Llama 3) invoked only for "Grey Zone" ambiguity or "Shadow Review" (auditing borderline safe texts).
4. **Agent 4 (Profiler)**: An algorithmic module tracking historical metadata to assign dynamic **Behavioral Risk Scores** to senders.
5. **Agent 5 (Orchestrator)**: The final decision-maker managing side effects: triggering WebSockets, issuing DB commits, and dispatching WhatsApp Webhook deletion requests.

---

## 🛠️ Technology Stack

| Layer | Technologies Used |
|-------|------------------|
| **Frontend UI** | Angular 21, TypeScript, TailwindCSS, PrimeNG, Chart.js |
| **Backend API** | Django 5.2, Django REST Framework, Channels (WebSockets) |
| **AI / NLP** | PyTorch, HuggingFace Transformers, Built-in Tokenizers |
| **LLM Provider** | Groq Cloud API (Llama 3.3 70B Versatile) |
| **WhatsApp Engine**| Evolution API v2 |
| **Data Persistence**| PostgreSQL (Core Data), Redis (Cache & WebSockets) |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Node.js v20+** & **Angular CLI**
- **Python 3.12+**
- **Evolution API** running locally on port `5002`
- **PostgreSQL** & **Redis**

### 2. Backend Setup
The backend requires the HuggingFace `.safetensors` model weights to be placed in `aegis-backend/ml_pipeline/models/`.

```bash
cd aegis-backend

# Initialize virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (from generated requirements.txt)
pip install -r requirements.txt

# Configure Environment Variables
cp .env.example .env
# Open .env and insert your GROQ_API_KEY, EVOLUTION_API_KEY, and DB URLs.

# Run migrations and start the ASGI dev server
python manage.py migrate
python manage.py runserver
```

### 3. Frontend Setup
```bash
cd aegis-frontend

# Install node modules
npm install

# Start the Angular development server
ng serve
```

Access the dashboard at `http://localhost:4200`.

---

## 🛡️ Key Features

- **Multi-Tenant Security**: Dedicated boundaries between Global Administrators and Parents monitoring their registered children.
- **Microsecond Latency**: Heavily optimized PyTorch pipeline and Redis caching ensures messages are intercepted $<500$ms.
- **Active Shield Response**: If a message is classified as `BLOCK` or `ESCALATE`, AEGIS commands WhatsApp to delete the message for everyone before the recipient sees it.
- **Shadow Review Protocol**: Borderline safe messages are silently forwarded to an LLM for secondary auditing, minimizing false negatives.
- **QR Device Pairing**: Parents can seamlessly link their child's WhatsApp directly from the dashboard using secure WebSocket QR-code generation based on Baileys.

---

## Authors

- **Mohamed ZNITA** — PFE Student
