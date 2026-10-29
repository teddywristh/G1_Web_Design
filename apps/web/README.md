# `apps/web` — Next.js Frontend Application

## Overview
`apps/web` contains the user-facing web application for the **Legal AI Assistant** platform. It provides an intuitive, high-performance interface for searching legal documents, navigating Articles and Clauses, interacting with AI research assistance, and verifying legal citations against original sources.

## Tech Stack
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript
- **Styling**: Vanilla CSS / CSS Modules / Design System Tokens
- **Shared Components**: `@legal-ai/ui` (imported from `packages/ui`)
- **State & Data Fetching**: React Server Components & client hooks

## Directory Structure (Planned in Issue #2)
```
apps/web/
├── public/                 # Static assets (favicons, logos, icons)
├── src/
│   ├── app/                # Next.js App Router pages and layouts
│   │   ├── layout.tsx      # Root application layout
│   │   ├── page.tsx        # Homepage / Search landing
│   │   └── globals.css     # Global styles & design tokens
│   ├── components/         # Web-specific UI & layout components
│   │   ├── layout/         # Header, Footer, Navigation, Sidebar
│   │   └── ui/             # Page-specific components
│   ├── lib/                # API client, utility functions, helpers
│   └── types/              # TypeScript interface & type definitions
├── .env.example            # Environment variables template
├── package.json            # Web dependencies and scripts
├── tsconfig.json           # TypeScript configuration
└── README.md
```

## Team Ownership & Responsibility
- **Primary Owner**: Frontend Team (@minhnm162, @teddywristh)
- **Responsibilities**:
  - User interface implementation and responsive layout.
  - Integration with backend REST API (`/api/v1/*`).
  - Interactive search, chat interface, and citation viewing experiences.
  - Client-side accessibility (a11y) and performance.

## Getting Started
Copy `.env.example` to `.env.local`:
```bash
cp .env.example .env.local
```
Install dependencies and run the development server (configured in Issue #2):
```bash
npm install
npm run dev
```
By default, the web client runs on `http://localhost:3000`.
