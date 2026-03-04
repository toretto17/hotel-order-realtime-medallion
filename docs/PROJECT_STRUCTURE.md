# How to create a new project with the correct name and add the docs

This page explains how to create a **new** project for this real-time order Medallion design and where to put **ARCHITECTURE.md** and **VIDEO_ANALYSIS.md**.

---

## 1. Project name

Use this name for the project / repository:

**`realtime-order-medallion`**

- Describes the domain (orders), pattern (medallion), and style (realtime).
- Keeps naming consistent across clones, forks, and new repos.

---

## 2. Folder layout for the new project

Create the following structure (you can add code/config later):

```
realtime-order-medallion/
├── README.md                 # Project name, one-line description, links to the two docs
├── ARCHITECTURE.md            # Full architecture (diagram, stack, Medallion, checklist)
├── docs/
│   ├── VIDEO_ANALYSIS.md      # Video breakdown and mapping to this design
│   └── PROJECT_STRUCTURE.md   # This file — how to create the project and add the docs
├── config/                    # (optional) pipeline.yaml, env examples
├── streaming/                 # (optional) Spark jobs
├── sql/                       # (optional) Gold-layer SQL
└── infrastructure/            # (optional) Terraform / IaC
```

---

## 3. Adding the two main files

### ARCHITECTURE.md

- **Place:** Project **root** (`realtime-order-medallion/ARCHITECTURE.md`).
- **Role:** Single source of truth for architecture (diagram, tech stack, Medallion layers, data models, exactly-once, checkpointing, DLQ, partitioning, CI/CD, IaC, production checklist).
- **When creating a new project:** Copy the full content of `ARCHITECTURE.md` from this repo into the root of your new project.

### VIDEO_ANALYSIS.md

- **Place:** **`docs/`** folder (`realtime-order-medallion/docs/VIDEO_ANALYSIS.md`).
- **Role:** Summary of the reference video (Databricks E2E), best practices, production gaps, and mapping from video concepts to this repo (e.g. Event Hub → Kafka, LakeFlow → Debezium + Kafka Connect).
- **When creating a new project:** Create a `docs/` directory and copy the full content of `VIDEO_ANALYSIS.md` there.

---

## 4. Step-by-step: create the new project

1. **Create the project folder**
   ```bash
   mkdir realtime-order-medallion
   cd realtime-order-medallion
   ```

2. **Create `docs/`**
   ```bash
   mkdir docs
   ```

3. **Add ARCHITECTURE.md**
   - Copy the entire contents of `ARCHITECTURE.md` from this repo.
   - Save as `realtime-order-medallion/ARCHITECTURE.md` (in the project root).

4. **Add VIDEO_ANALYSIS.md**
   - Copy the entire contents of `docs/VIDEO_ANALYSIS.md` from this repo.
   - Save as `realtime-order-medallion/docs/VIDEO_ANALYSIS.md`.

5. **Add README.md**
   - Create a short README with the project name, one-line description, and links to:
     - `ARCHITECTURE.md`
     - `docs/VIDEO_ANALYSIS.md`
     - `docs/PROJECT_STRUCTURE.md` (this file).

6. **(Optional)** Copy `docs/PROJECT_STRUCTURE.md` into your new project’s `docs/` so the instructions stay with the repo.

---

## 5. Summary

| What | Where |
|------|--------|
| Project name | `realtime-order-medallion` |
| Architecture doc | **Root:** `ARCHITECTURE.md` |
| Video analysis doc | **Under docs:** `docs/VIDEO_ANALYSIS.md` |
| This guide | `docs/PROJECT_STRUCTURE.md` |

After this, you have a new project with the correct name and both key docs in the right places. You can then add `config/`, `streaming/`, `sql/`, and `infrastructure/` as you implement the design.
