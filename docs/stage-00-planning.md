# Stage 0: Planning

**Date:** 2026-11-25 · **Status:** Done (reviewed and approved)

## What we did

We planned the project before writing any code. No code exists yet, only planning documents.

## What we decided (from the interview)

| Question | Decision | Why it matters |
|---|---|---|
| Who uses it? | A **denials/AR analyst** | Everything is built around their daily worklist |
| What should it help them do? | **Predict** which claims will be denied, then **rank** which to work first | Two parts: a model and a priority score |
| Where does the data come from? | **Our own Python generator** that makes fake claims | No real patient data, ever |
| How much data? | About **100,000 claims over 18 months** | Enough to train a real model and still run fast on a laptop |
| Biggest risk? | **Too much to build in the time available** | So we build a simple version end to end first, then improve it |
| How long? | About **3 weeks**. Power BI last and optional | Power BI only runs on Windows; the rest works on a Mac |

## The files we created

- **`PRD.md`**: what the product does, who it is for, what is in and out of scope, and what "done" means.
- **`spec/plan.md`**: how it is built: the architecture diagram, folder layout, and 18 ordered steps.
- **`TASK.md`**: the same steps, each with a clear checklist ("acceptance criteria") and a status.
- **`CLAUDE.md`**: rules for the AI assistant: fake data only, never touch secrets, one step at a time, always show real test output.
- **`.gitignore`**: keeps secrets, generated data and local environments out of GitHub.

## How it will work (in plain words)

1. A script makes fake claims and fake insurance replies (some paid, some denied).
2. dbt cleans and organizes that data into tables.
3. A model learns which kinds of claims tend to get denied.
4. Each claim gets a score: *chance of denial × dollars × chance we can recover it*.
5. An API serves the scores, and a Streamlit web page shows the analyst a ranked to-do list.

## What is next

**Step 1: Scaffold.** Set up the Python project, the linter, the test runner, and a GitHub Actions check that runs on every push.
