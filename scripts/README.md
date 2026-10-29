# `scripts/` — Development Utilities & Scripts

## Overview
`scripts/` houses cross-cutting development automation, data ingestion tools, local environment preflight checks, and seed utilities.

## Planned Utilities
- **`preflight.py` / `check-env.sh`** (Issue #13): Validates local developer machine prerequisites (Node.js, Python, Docker, PostgreSQL, Redis connectivity) and environment configuration without printing secrets.
- **`seed.py`** (Issue #5 / #9): Idempotently seeds initial development data, test accounts, and sample legal documents (e.g. Vietnamese Labor Code, Civil Code provisions).

## Team Ownership & Responsibility
- **Primary Owner**: Tooling & DevOps (@teddywristh, @leducminh290506-eng)
- **Responsibilities**:
  - Providing lightweight, cross-platform scripts for setup automation.
  - Ensuring scripts exit with standard exit codes (0 for success, non-zero for failure).
  - Preventing data loss or destruction in user environments.
