# 🚀 resume_py: Agentic Job Application Orchestrator

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Architecture: Agentic](https://img.shields.io/badge/Architecture-Agentic%20RAG-purple.svg)](#architecture)
[![Automation: Selenium](https://img.shields.io/badge/Automation-Selenium%20%2F%20Playwright-emerald.svg)](#tech-stack)

**resume_py** is a high-performance, LLM-driven autonomous agent designed to solve the "Job Search Fatigue" by automating the end-to-end application lifecycle. Unlike simple form-fillers, `resume_py` uses **Agentic Reasoning** to handle dynamic UI changes, solve multi-step application logic, and tailor content for 25+ enterprise portals.

---

## 🌟 Key Achievements
*   **76+ Successful Matches**: High-precision matching using LLM-based ATS scoring.
*   **25+ Managed Portals**: Robust automation for Workday, Greenhouse, Lever, and custom company portals.
*   **5,000+ LOC**: A stable, modular codebase optimized for long-running execution (~90m sessions).
*   **70% Effort Reduction**: Eliminates manual data entry and site navigation.

---

## 🏛️ Architecture & Intelligence

`resume_py` operates on a **Stateful Agentic Workflow**:

1.  **RAG Engagement**: Compares your master resume against raw job descriptions using a vector-based Retrieval-Augmented Generation (RAG) pipeline to identify "Gaps vs. Strengths."
2.  **LLM Reasoning Engine**: Utilizes GPT-4/Gemini to interpret complex application questions (e.g., "Describe a time you...") and generates context-aware, truthful responses.
3.  **Dynamic Orchestration**: Uses Selenium and Playwright with custom retry/backoff logic to navigate 25+ unique UI architectures.
4.  **Deterministic Guardrails**: Validates all generated content against Pydantic schemas before injection to ensure zero "hallucinations" in critical application fields.

---

## 🛠️ Tech Stack

| Category | Technologies |
| :--- | :--- |
| **Core** | Python 3.10+, Selenium, Playwright |
| **AI/ML** | GPT-4, Gemini Pro, LangChain, FAISS (Vector DB) |
| **Data** | Pydantic, Beautiful Soup, Asyncio |
| **DevOps** | Docker, GitHub Actions (CI/CD) |

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   WebDriver for Chrome/Firefox
*   OpenAI or Google Vertex AI Credentials

### Installation
```bash
git clone [https://github.com/BNTiyan/resume_py.git](https://github.com/BNTiyan/resume_py.git)
cd resume_py
pip install -r requirements.txt
