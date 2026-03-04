# Realtime Order Medallion

**Production-grade real-time order processing using Medallion Architecture (Bronze, Silver, Gold).**  
Cloud-agnostic · Kafka + Spark Structured Streaming · PostgreSQL optional.

---

## Project name

**Repository / project name:** `realtime-order-medallion`

- **realtime** — streaming, near real-time analytics  
- **order** — domain (order processing and analytics)  
- **medallion** — Bronze → Silver → Gold architecture  

Use this same name when cloning, creating a new repo, or referring to the project.

---

## Where the main docs live

| Document | Location | Purpose |
|----------|----------|--------|
| **Architecture & design** | [ARCHITECTURE.md](./ARCHITECTURE.md) | High-level diagram, tech stack, Medallion layers, data models, exactly-once, checkpointing, DLQ, CI/CD, IaC, production checklist. |
| **Video analysis** | [docs/VIDEO_ANALYSIS.md](./docs/VIDEO_ANALYSIS.md) | Breakdown of the Databricks E2E video: best practices, gaps, and mapping to this (generic) design. |
| **How to create this project** | [docs/PROJECT_STRUCTURE.md](./docs/PROJECT_STRUCTURE.md) | How to create a new project with the correct name and add these two files. |
| **File-by-file guide** | [docs/FILE_BY_FILE_GUIDE.md](./docs/FILE_BY_FILE_GUIDE.md) | What each file does, with code examples and end-to-end flow. |

---

## Learning path (step-by-step)

**Build and learn incrementally:** [docs/LEARNING_PATH.md](./docs/LEARNING_PATH.md) defines a lesson-by-lesson curriculum. Start with Lesson 1 (data contract & config), then Bronze → Silver → Gold → DLQ → exactly-once → orchestration. Each lesson has clear concepts and deliverables so you learn deeply and can speak to it in interviews.

## Quick start

1. Read **ARCHITECTURE.md** for the full design.  
2. Read **docs/LEARNING_PATH.md** and start with **Lesson 1**.  
3. Read **docs/VIDEO_ANALYSIS.md** to see how the reference video maps to this repo.  
4. Use **docs/PROJECT_STRUCTURE.md** to spin up a new project with the same layout and docs.
