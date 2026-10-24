# `packages/ui` — Shared UI Component Library

## Overview
`packages/ui` provides reusable, framework-agnostic or React-based UI components, typography styles, and design system tokens shared across the monorepo applications.

## Purpose & Scope
- Centralizes shared design elements: buttons, input fields, modals, document viewers, badges (e.g., legal status indicators: "In Effect", "Amended", "Expired").
- Enforces consistent styling, accessibility standards, and visual polish across all web views.
- Prevents duplication of CSS and React components between different pages or future client applications.

## Directory Structure (Planned)
```
packages/ui/
├── src/
│   ├── components/         # Button, Input, Modal, Badge, CitationCard, etc.
│   ├── styles/             # Design tokens, variables, reset styles
│   └── index.ts            # Public export entrypoint
├── package.json
├── tsconfig.json
└── README.md
```

## Team Ownership & Responsibility
- **Primary Owner**: Frontend Team (@minhnm162, @teddywristh)
- **Responsibilities**:
  - Developing and maintaining shared accessible UI components.
  - Ensuring consistent design tokens (colors, spacing, typography).
  - Versioning and exporting clean component interfaces.
