# Project: stockDashboard

A full-stack application providing stock OHLCV data and technical indicators.

## Architecture

- **Backend**: Python/FastAPI application.
  - Located in `/src/backend`.
  - Structured into `routers/` (endpoint definitions) and `services/` (business/data logic).
  - Uses `alpaca-py` for data fetching and `pandas` for indicator calculations.
- **Frontend**: React (Vite, TypeScript, TailwindCSS).
  - Located in `/src/frontend`.
  - Uses `lightweight-charts` for financial charting.

## Development Standards

### Backend
- **Framework**: FastAPI.
- **Dependency Management**: `uv`.
- **Testing**: `pytest`. Run tests using `pytest src/backend/tests`.
- **Style**: Adhere to PEP 8.
- **Modularization**: Keep endpoint logic thin in `routers/` by delegating to `services/`.

### Frontend
- **Framework**: React (Vite).
- **Styling**: TailwindCSS (Mandatory). All styling must use Tailwind utility classes; avoid custom CSS or inline styles unless necessary.
- **Linting**: ESLint (configured in `eslint.config.js`). Run using `npm run lint` in the `src/frontend` directory.
- **Component Pattern**: Prefer small, reusable functional components.

## Workflow

- **Backend Changes**:
  - Add new endpoints in `/src/backend/routers/`.
  - Add logic in `/src/backend/services/`.
  - Always add/update tests in `/src/backend/tests/`.
- **Frontend Changes**:
  - Add new components in `/src/frontend/src/components/`.
  - Add new pages in `/src/frontend/src/pages/`.
  - Run linting (`npm run lint`) before committing.
