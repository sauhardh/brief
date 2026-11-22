# 📊 Market Researcher — Multi-Agent Brief Generator

An autonomous multi-agent research pipeline that turns any market, industry, or company topic into an evidence-grounded research brief. Built with Python, Streamlit, and an agent workflow powered by Groq (or local Ollama).

---

## 💡 How It Works

Instead of relying on a single prompt to do research and analysis all at once, this system splits the work across specialized agents with an automated review loop:

```
                  ┌──────────────────────┐
                  │   User Input Query   │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ 1. Researcher Agent  │
                  │ (SearXNG / DuckDuckGo)
                  └──────────┬───────────┘
                             │ Evidence points
                             ▼
                  ┌──────────────────────┐
                  │  2. Analyst Agent    │
                  │ (Drafts Brief JSON)  │
                  └──────────┬───────────┘
                             │ Draft brief
                             ▼
                  ┌──────────────────────┐
                  │   3. Critic Agent    │
                  │  (Fact-Check Review) │
                  └──────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
       [Approved]                        [Revision Required]
            │                                 │
     Final Output                    Analyst Revises
                                              │
                                     Critic Re-evaluates
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                         [Approved]                  [Still Not Approved]
                              │                               │
                        Final Output                  Restart from scratch
                                                      (1 final attempt)
```

1. **Orchestrator**: Determines the LLM provider (Groq API vs. local Ollama) and tracks the shared workflow state across iterations.
2. **Researcher**: Converts topics into high-intent search queries and pulls live web results. It uses a local **SearXNG** Docker container (keyless, aggregating Google + Bing + DDG) with an automatic fallback to **DuckDuckGo (`ddgs`)**.
3. **Analyst**: Synthesizes raw snippets into a concise, evidence-grounded brief containing a summary, top 2 competitors, key observations, and data gaps.
4. **Critic**: Fact-checks the draft against the collected findings. If claims aren't grounded, it triggers a structured revision loop.

---

## 🛠️ Prerequisites

* **Python 3.10+** (Python 3.13 recommended)
* **Docker** (optional, recommended — used to run SearXNG automatically for web search)
* **LLM Provider**:
  * **Option A (Cloud)**: A free [Groq Cloud API Key](https://console.groq.com)
  * **Option B (Local)**: [Ollama](https://ollama.com) running on your machine (e.g. `mistral:latest` or `llama3.2`)

---

## 🚀 Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/brief.git
cd brief
```

### 2. Set up virtual environment

Using `uv` (recommended):
```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

Or using standard `pip`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r pyproject.toml
```

### 3. Configure environment variables

Create a `.env` file in the root directory:

```bash
touch .env
```

Add your configuration:

```env
# --- Option 1: Groq API (Fast cloud inference) ---
OPENAI_API_KEY=gsk_your_groq_api_key_here
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-20b

# --- Option 2: Local Ollama (Uncomment if using Ollama without API key) ---
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=mistral:latest
```

> **Note:** If `OPENAI_API_KEY` is present, the app automatically connects to Groq. If it's missing or commented out, it automatically connects to your local Ollama instance.

---

## 🏃 Running the Application

Launch the Streamlit app:

```bash
streamlit run app/main.py
```

Open your browser at `http://localhost:8501`.

* On the first run, the app will automatically spin up a local SearXNG Docker container in the background to handle search queries without requiring any search API keys.

---

## 📋 Sample Output

**Query entered:**  
> *"Analyze the food delivery market in Nepal"*

```markdown
### 1. Executive Summary
Nepal's online food delivery market has experienced rapid adoption, driven primarily by smartphone penetration, digital wallet growth (eSewa, Khalti), and changing urban consumer habits in the Kathmandu Valley. While the industry started with specialized delivery players, recent years have seen stiff competition from ride-hailing super-apps integrating food delivery into their broader mobility ecosystems.

### 2. Main Competitors (Up to 2)
🏢 Foodmandu
The pioneer of online food delivery in Nepal (founded in 2010), holding an extensive restaurant partner network and commanding strong brand loyalty for premium dining delivery.

🏢 Pathao Food
A ride-hailing turned super-app that leveraged its existing two-wheeler rider fleet to aggressively capture market share through faster delivery times and competitive pricing.

### 3. Key Observations
- Geographic concentration remains high in Kathmandu, Lalitpur, and Pokhara, with gradual expansion into Tier-2 cities like Butwal and Biratnagar.
- Digital payments have largely replaced cash-on-delivery (COD) as QR-code interoperability (Fonepay) scaled nationwide.
- High restaurant commission rates (15%–25%) and fuel price volatility remain the primary margin challenges for platform operators.
- Cloud kitchens and platform-exclusive dining partnerships are emerging as primary growth strategies.

### 4. Sources Cited
- https://kathmandupost.com/money/2023/food-delivery-platforms-growth
- https://www.nepalitimes.com/business/the-rise-of-nepal-food-apps
- https://techlekh.com/foodmandu-vs-pathao-food-market-share

### 5. Missing / Uncertain Information
- Exact annual market revenue numbers are unverified due to private ownership of leading companies.
- Unit economics per order (average order value vs. rider payout) are not publicly disclosed.

Analyst Confidence Level: High
```

---

## 📁 Project Structure

```
brief/
├── app/
│   ├── agents/
│   │   ├── analyst.py         # Synthesizes research into structured JSON brief
│   │   ├── critic.py          # Fact-checker that validates claims and checks rules
│   │   ├── orchestrator.py    # Workflow controller & provider selector
│   │   └── researcher.py      # Query optimizer & web search coordinator
│   ├── main.py                # Streamlit UI & revision loop execution
│   ├── searxng_manager.py     # Auto-lifecycle manager for SearXNG Docker container
│   └── state.py               # Pydantic state models (Analysis, Criticism, WorkflowState)
├── pyproject.toml             # Project dependencies and packaging
├── .gitignore
└── README.md
```

---

## 🛡️ License

MIT License. Free to use, modify, and build upon.
