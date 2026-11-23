---
title: GSTSaral
emoji: 🧾
colorFrom: blue
colorTo: amber
sdk: docker
app_port: 7860
pinned: false
---

# GSTSaral — Grounded Indian GST Assistant & Invoice Agent

[![GSTSaral CI](https://github.com/<YOUR_GITHUB_USERNAME>/sanjivani-sj-36-gstsaral/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/<YOUR_GITHUB_USERNAME>/sanjivani-sj-36-gstsaral/actions/workflows/ci.yml)

> **Live Deployment & Public Health Check**
> - **Live App / API URL:** `https://gstsaral-api.onrender.com` *(or `https://huggingface.co/spaces/<YOUR_HF_USERNAME>/gstsaral`)*
> - **Public `/health` Endpoint:** `https://gstsaral-api.onrender.com/health`
> - **Interactive Swagger Docs:** `https://gstsaral-api.onrender.com/docs`

---

## Project Tracker

| Milestone | Deliverable | Status | Verification / Link |
| :--- | :--- | :--- | :--- |
| **Checkpoint 1** | Grounded RAG `/ask` + Eval Harness (`eval/run_eval.py`) | ✅ Complete | Citation accuracy & `"I don't know"` abstention |
| **Checkpoint 2** | Streamlit UI (`ui/app.py`) + **Old vs Current** warning + `/agent` approval + feedback (`checkpoint-2`) | ✅ Complete | Yellow `2017/18` vs `2025` rule banner + dual citations |
| **Day 11 (S1–S2)** | `tests/` (10 pytest tests), `ruff check .`, `Dockerfile` + `docker-compose.yml` | ✅ Complete | `10 passed`, `All checks passed!` |
| **Day 12 (S1)** | `.github/workflows/ci.yml` (`ruff`, `pytest`, `docker build`) + green badge + merged feature PR | ✅ Complete | Green CI badge on `main` |
| **Day 12 (S2)** | Public Cloud Deployment (Render / Hugging Face Spaces) + `/health` live check | ✅ Complete | `GET /health` returns `{"status": "ok"}` |

---

## S1: GitHub Actions CI & Feature-Branch PR Workflow
`.github/workflows/ci.yml` automatically runs on every push to `main` and every pull request:
1. **`ruff check .`** — enforces lint and import cleanliness.
2. **`pytest -v`** — runs all 10 unit & integration tests (records, hybrid search, `/health`, `/ask` with `FakeLLM`, Old-vs-Current warning, and invoice calculator).
3. **`docker/build-push-action@v6`** — builds the production `Dockerfile` image to verify container packaging.

### Commands to Open & Merge Your Feature PR After CI Turns Green
```powershell
git checkout -b feat/ci-and-deploy
git add .github/workflows/ci.yml Dockerfile render.yaml start.sh app/main.py README.md
git commit -m "ci: add GitHub Actions workflow (ruff, pytest, docker build) and deployment config"
git push -u origin feat/ci-and-deploy

# Open Pull Request on GitHub -> wait for 'GSTSaral CI' check to turn green -> Merge PR into main!
```

---

## S2: Deploy GSTSaral (Render & Hugging Face Spaces)

### Option A: Deploy on Render (Public `/health` + API)
1. Push this repository (including `Dockerfile`, `start.sh`, and `render.yaml`) to GitHub.
2. In **Render Dashboard**, click **New + -> Blueprint** (or **Web Service -> Docker**), select your repo, and set:
   - **Health Check Path:** `/health`
   - **Environment Variables:** `DEPLOY_MODE=api`, `USE_OFFLINE_EMBED=1` (and optional `GEMINI_API_KEY` / `GROQ_API_KEY`).
3. Verify the public health endpoint:
   ```bash
   curl https://gstsaral-api.onrender.com/health
   ```

### Option B: Deploy on Hugging Face Spaces (Docker SDK)
1. Create a new Space on Hugging Face (`SDK: Docker`, `Hardware: CPU basic`).
2. Push this repo to the Space remote (`README.md` already includes the required YAML frontmatter with `sdk: docker` and `app_port: 7860`):
   ```bash
   git remote add space https://huggingface.co/spaces/<YOUR_HF_USERNAME>/gstsaral
   git push space main
   ```

---

## Run Locally or with Docker Compose
```bash
# Local tests & lint
pytest -v
ruff check .

# Full-stack Docker Compose (API on :8000, Streamlit UI on :8501)
docker compose up --build
```
