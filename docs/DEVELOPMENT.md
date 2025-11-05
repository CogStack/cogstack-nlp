# Development Workflow & Standards

## Project Overview

**Project Name**: CogStack NLP Full Potential UI
**Version**: 1.0.0 (in development)
**Tech Stack**: Vue 3 / TypeScript / FastAPI / PostgreSQL / Elasticsearch / Docker

This document defines the development workflow, technical standards, and infrastructure setup for the Full Potential UI project.

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Project Structure](#project-structure)
3. [Branching Strategy](#branching-strategy)
4. [Development Workflow](#development-workflow)
5. [Testing Strategy](#testing-strategy)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Deployment Process](#deployment-process)
8. [Code Review Guidelines](#code-review-guidelines)

---

## Development Environment Setup

### Prerequisites

**Required**:
- Node.js >= 18.x
- Python >= 3.10
- Docker >= 24.x
- Docker Compose >= 2.x
- Git >= 2.x

**Recommended**:
- VS Code with extensions:
  - ESLint
  - Prettier
  - Volar (Vue)
  - Python
  - Docker

### Initial Setup

```bash
# 1. Clone repository
git clone https://github.com/CogStack/cogstack-nlp.git
cd cogstack-nlp

# 2. Create development branch
git checkout -b develop origin/main

# 3. Install frontend dependencies
cd full-potential-ui/frontend
npm install

# 4. Install backend dependencies
cd ../backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 5. Set up environment variables
cp .env.example .env
# Edit .env with your local configuration

# 6. Start development services
docker-compose -f docker-compose.dev.yml up -d

# 7. Run database migrations
python manage.py migrate

# 8. Create superuser
python manage.py createsuperuser

# 9. Start development servers
# Terminal 1 (Frontend):
cd full-potential-ui/frontend
npm run dev

# Terminal 2 (Backend):
cd full-potential-ui/backend
python manage.py runserver

# Access application at http://localhost:5173
```

### Environment Variables

**`.env` template**:

```bash
# Application
NODE_ENV=development
API_BASE_URL=http://localhost:8000

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/cogstack_dev
DATABASE_POOL_SIZE=10

# MedCAT Service
MEDCAT_SERVICE_URL=http://localhost:5000
MEDCAT_API_KEY=your_api_key_here

# Elasticsearch
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=patients

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET=your-jwt-secret-here
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Feature Flags
ENABLE_REAL_TIME_ALERTS=true
ENABLE_RELATIONSHIP_EXTRACTION=true
ENABLE_COHORT_BUILDER=true

# Performance
CACHE_TTL=300
API_RATE_LIMIT=100
```

---

## Project Structure

```
cogstack-nlp/
├── full-potential-ui/
│   ├── frontend/                 # Vue 3 frontend application
│   │   ├── src/
│   │   │   ├── components/       # Reusable UI components
│   │   │   │   ├── common/       # Shared components
│   │   │   │   ├── clinical/     # Clinical dashboard components
│   │   │   │   ├── research/     # Research workbench components
│   │   │   │   └── governance/   # Governance portal components
│   │   │   ├── views/            # Page-level components
│   │   │   ├── services/         # API clients
│   │   │   ├── stores/           # Pinia state management
│   │   │   ├── composables/      # Vue composables
│   │   │   ├── types/            # TypeScript type definitions
│   │   │   ├── utils/            # Utility functions
│   │   │   └── router/           # Vue Router configuration
│   │   ├── tests/
│   │   │   ├── unit/             # Unit tests
│   │   │   ├── integration/      # Integration tests
│   │   │   └── e2e/              # End-to-end tests
│   │   ├── public/               # Static assets
│   │   └── package.json
│   │
│   ├── backend/                  # FastAPI backend application
│   │   ├── app/
│   │   │   ├── api/              # API endpoints
│   │   │   │   ├── v1/
│   │   │   │   │   ├── clinical/
│   │   │   │   │   ├── research/
│   │   │   │   │   └── governance/
│   │   │   ├── core/             # Core configuration
│   │   │   ├── models/           # Database models
│   │   │   ├── schemas/          # Pydantic schemas
│   │   │   ├── services/         # Business logic
│   │   │   ├── clients/          # External API clients
│   │   │   │   └── medcat/       # MedCAT service client
│   │   │   └── utils/            # Utility functions
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── fixtures/
│   │   ├── alembic/              # Database migrations
│   │   └── requirements.txt
│   │
│   └── docker/                   # Docker configuration
│       ├── docker-compose.dev.yml
│       ├── docker-compose.prod.yml
│       ├── Dockerfile.frontend
│       └── Dockerfile.backend
│
├── docs/                         # Project documentation
│   ├── agents.md                 # AI development guidelines
│   ├── DEVELOPMENT.md            # This file
│   ├── PROJECT_PLAN.md           # Sprint breakdown
│   ├── design/                   # Design documents
│   │   ├── architecture.md
│   │   ├── api-spec.md
│   │   ├── database-schema.md
│   │   └── ui-components.md
│   ├── prd/                      # Product requirements
│   │   ├── sprint-1/
│   │   ├── sprint-2/
│   │   └── ...
│   └── api/                      # API documentation
│       └── openapi.yaml
│
└── .github/
    └── workflows/                # GitHub Actions
        ├── ci.yml
        ├── cd.yml
        └── pr-checks.yml
```

---

## Branching Strategy

### Branch Types

```
main
  ├── Production-ready code
  ├── Tagged releases (v1.0.0, v1.1.0, etc.)
  └── Protected (requires PR + reviews)

develop
  ├── Integration branch for features
  ├── Always deployable to staging
  └── Protected (requires PR)

feature/*
  ├── feature/sprint-1-patient-search
  ├── feature/sprint-2-timeline-view
  └── Created from 'develop', merged back to 'develop'

bugfix/*
  ├── bugfix/fix-search-pagination
  └── Created from 'develop', merged back to 'develop'

hotfix/*
  ├── hotfix/critical-security-fix
  └── Created from 'main', merged to both 'main' and 'develop'

release/*
  ├── release/v1.0.0
  └── Created from 'develop', merged to 'main' and tagged
```

### Branch Naming Conventions

```bash
# Feature branches
feature/sprint-{N}-{brief-description}
feature/sprint-1-patient-search
feature/sprint-2-timeline-view

# Bug fixes
bugfix/{issue-number}-{brief-description}
bugfix/123-fix-search-error

# Hotfixes
hotfix/{version}-{brief-description}
hotfix/1.0.1-security-patch

# Release branches
release/v{major}.{minor}.{patch}
release/v1.0.0
```

---

## Development Workflow

### Starting a New Sprint

```bash
# 1. Ensure develop is up to date
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b feature/sprint-1-patient-search

# 3. Create ticket branches as needed (optional)
git checkout -b feature/sprint-1-patient-search/ticket-1

# 4. Start development
```

### Daily Development Cycle

```bash
# 1. Start of day - pull latest changes
git checkout develop
git pull origin develop
git checkout feature/sprint-1-patient-search
git merge develop  # Keep feature branch updated

# 2. Write tests first
# - Create test files in tests/
# - Run: npm test (frontend) or pytest (backend)
# - Tests should FAIL (red phase)

# 3. Implement feature
# - Write code to make tests pass
# - Run tests: npm test / pytest
# - Tests should PASS (green phase)

# 4. Refactor if needed
# - Improve code quality
# - Tests should still pass

# 5. Commit changes
git add .
git commit -m "feat(patient-search): implement search API endpoint

[Agent-generated code]

Changes:
- Added PatientSearchService with query() method
- Implemented MedCAT client integration
- Added input validation for search parameters

Rationale:
- Implements PRD Sprint 1, Section 3.2
- Uses MedCAT service for concept-based search
- Validates input to prevent API errors

Tests:
- Added 15 unit tests for PatientSearchService
- Added 5 integration tests with mock MedCAT
- Test coverage: 92%

AI Context:
- PRD: docs/prd/sprint-1/patient-search.md
- Session: Sprint 1, Ticket 2
- Review status: Pending"

# 6. Push to remote
git push origin feature/sprint-1-patient-search

# 7. Repeat for next ticket/task
```

### Creating a Pull Request

```bash
# 1. Ensure all tests pass
npm test          # Frontend
pytest            # Backend
npm run lint      # Check code style
npm run type-check # TypeScript checks

# 2. Update documentation
# - Update README if needed
# - Update API docs if endpoints changed
# - Update design docs if architecture changed

# 3. Push final changes
git push origin feature/sprint-1-patient-search

# 4. Create PR on GitHub
# - Title: "Sprint 1: Patient Search & Discovery"
# - Description: Link to PRD, list deliverables, add screenshots
# - Reviewers: Add team members
# - Labels: Add appropriate labels (feature, sprint-1, etc.)

# 5. Address review comments
# - Make requested changes
# - Commit: "fix: address PR review comments"
# - Push updates

# 6. Merge after approval
# - Squash and merge (preferred for features)
# - Delete feature branch after merge
```

---

## Testing Strategy

### Test Pyramid

```
      ╱╲          E2E Tests (10%)
     ╱  ╲         - Full user workflows
    ╱    ╲        - Critical paths only
   ╱──────╲
  ╱        ╲      Integration Tests (30%)
 ╱  ██████  ╲     - API endpoints
╱    ████    ╲    - Service interactions
────────────────
████████████████  Unit Tests (60%)
████████████████  - Pure functions
████████████████  - Component logic
                  - Service methods
```

### Frontend Testing

**Unit Tests** (Vitest):

```typescript
// tests/unit/services/PatientSearchService.test.ts
import { describe, it, expect, vi } from 'vitest'
import { PatientSearchService } from '@/services/PatientSearchService'

describe('PatientSearchService', () => {
  describe('query()', () => {
    it('should search patients by concept', async () => {
      // Arrange
      const service = new PatientSearchService()
      const params = { concept: 'atrial flutter' }

      // Act
      const results = await service.query(params)

      // Assert
      expect(results).toBeDefined()
      expect(results).toHaveLength(47)
      expect(results[0]).toHaveProperty('mrn')
    })
  })
})
```

**Component Tests** (Vitest + Testing Library):

```typescript
// tests/unit/components/PatientSearch.test.ts
import { render, fireEvent, screen } from '@testing-library/vue'
import PatientSearch from '@/components/clinical/PatientSearch.vue'

describe('PatientSearch Component', () => {
  it('should display search results', async () => {
    // Arrange
    render(PatientSearch)

    // Act
    const input = screen.getByPlaceholderText('Search patients...')
    await fireEvent.update(input, 'atrial flutter')
    await fireEvent.click(screen.getByText('Search'))

    // Assert
    await screen.findByText('47 patients found')
    expect(screen.getByText('Smith, John')).toBeInTheDocument()
  })
})
```

**E2E Tests** (Playwright):

```typescript
// tests/e2e/patient-search.spec.ts
import { test, expect } from '@playwright/test'

test('patient search workflow', async ({ page }) => {
  // Navigate to app
  await page.goto('http://localhost:5173')

  // Login
  await page.fill('[data-testid="username"]', 'testuser')
  await page.fill('[data-testid="password"]', 'password')
  await page.click('[data-testid="login-btn"]')

  // Navigate to patient search
  await page.click('[data-testid="clinical-dashboard"]')

  // Perform search
  await page.fill('[data-testid="search-input"]', 'atrial flutter')
  await page.click('[data-testid="search-btn"]')

  // Verify results
  await expect(page.locator('[data-testid="result-count"]')).toContainText('47 patients')
  await expect(page.locator('[data-testid="patient-list"]')).toBeVisible()
})
```

### Backend Testing

**Unit Tests** (pytest):

```python
# tests/unit/services/test_patient_search_service.py
import pytest
from app.services.patient_search_service import PatientSearchService
from app.schemas.patient_search import PatientSearchQuery

@pytest.fixture
def search_service():
    return PatientSearchService()

def test_search_patients_by_concept(search_service):
    # Arrange
    query = PatientSearchQuery(concept="atrial flutter")

    # Act
    results = search_service.search(query)

    # Assert
    assert len(results) == 47
    assert results[0].mrn is not None
    assert results[0].annotations is not None
```

**Integration Tests** (pytest + TestClient):

```python
# tests/integration/api/test_patient_search_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_patient_search_endpoint():
    # Arrange
    payload = {
        "concept": "atrial flutter",
        "filters": {"temporal": "current"}
    }

    # Act
    response = client.post("/api/v1/patients/search", json=payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 47
```

### Test Coverage Requirements

**Minimum Coverage**:
- Overall: 80%
- Critical paths (auth, data processing): 100%
- New code: 90%

**Coverage Reports**:

```bash
# Frontend
npm run test:coverage
# Opens coverage/index.html

# Backend
pytest --cov=app --cov-report=html
# Opens htmlcov/index.html
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

**`.github/workflows/ci.yml`**:

```yaml
name: CI

on:
  pull_request:
    branches: [develop, main]
  push:
    branches: [develop, main]

jobs:
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: npm ci
        working-directory: ./full-potential-ui/frontend
      - name: Lint
        run: npm run lint
        working-directory: ./full-potential-ui/frontend
      - name: Type check
        run: npm run type-check
        working-directory: ./full-potential-ui/frontend
      - name: Unit tests
        run: npm test -- --coverage
        working-directory: ./full-potential-ui/frontend
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
        working-directory: ./full-potential-ui/backend
      - name: Lint
        run: pylint app/
        working-directory: ./full-potential-ui/backend
      - name: Type check
        run: mypy app/
        working-directory: ./full-potential-ui/backend
      - name: Unit tests
        run: pytest --cov=app --cov-report=xml
        working-directory: ./full-potential-ui/backend
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Snyk
        uses: snyk/actions/node@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [frontend-tests, backend-tests]
    steps:
      - uses: actions/checkout@v3
      - name: Start services
        run: docker-compose -f docker-compose.test.yml up -d
      - name: Run E2E tests
        run: npm run test:e2e
        working-directory: ./full-potential-ui/frontend
      - name: Stop services
        run: docker-compose -f docker-compose.test.yml down
```

### PR Checks (Required to Pass)

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage ≥ 80%
- [ ] Linting passes (no errors)
- [ ] Type checking passes (TypeScript/mypy)
- [ ] Security scan passes (Snyk)
- [ ] E2E tests pass (if applicable)
- [ ] Build succeeds
- [ ] Documentation updated

---

## Deployment Process

### Staging Deployment

**Automatic** on merge to `develop`:

```yaml
# .github/workflows/cd-staging.yml
name: Deploy to Staging

on:
  push:
    branches: [develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker images
        run: docker-compose -f docker-compose.prod.yml build
      - name: Push to registry
        run: |
          docker tag full-potential-ui-frontend:latest registry.cogstack.org/full-potential-ui-frontend:staging
          docker push registry.cogstack.org/full-potential-ui-frontend:staging
      - name: Deploy to staging
        run: |
          ssh deploy@staging.cogstack.org "cd /opt/full-potential-ui && docker-compose pull && docker-compose up -d"
```

**Staging URL**: https://staging.full-potential.cogstack.org

### Production Deployment

**Manual approval required**:

1. Create release branch: `release/v1.0.0`
2. Update version numbers
3. Create PR to `main`
4. After approval, merge and tag
5. Manual trigger of production deployment

```bash
# Create release
git checkout develop
git pull origin develop
git checkout -b release/v1.0.0

# Update versions
# - package.json
# - pyproject.toml
# - CHANGELOG.md

# Commit and PR
git commit -am "chore: bump version to 1.0.0"
git push origin release/v1.0.0
# Create PR to main

# After merge, tag release
git checkout main
git pull origin main
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# Trigger production deployment (manual GitHub Action)
```

---

## Code Review Guidelines

### Reviewer Checklist

**Code Quality**:
- [ ] Code follows project style guide
- [ ] No code smells (duplication, long methods, etc.)
- [ ] Proper error handling
- [ ] No hardcoded values (use config)
- [ ] Meaningful variable/function names

**Testing**:
- [ ] Tests exist and are comprehensive
- [ ] Tests actually test the functionality
- [ ] Edge cases covered
- [ ] Coverage meets requirements (≥80%)

**Security**:
- [ ] No hardcoded credentials
- [ ] Input validation present
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] CSRF protection
- [ ] PHI handling compliant

**Documentation**:
- [ ] Code is self-documenting or commented
- [ ] API changes documented
- [ ] README updated if needed

**Architecture**:
- [ ] Follows established patterns
- [ ] No tight coupling
- [ ] Reusable components
- [ ] Aligns with PRD

### Review Comments Format

**Good Comment**:
```
Line 45: Consider extracting this logic to a separate function for reusability.

Suggestion:
```typescript
function validateSearchParams(params: SearchParams): boolean {
  return params.concept && params.concept.length > 2
}
```

**Bad Comment**:
```
"This code is bad"
```

### Approval Process

1. **Self-review**: Author reviews own PR before requesting review
2. **Automated checks**: All CI/CD checks must pass
3. **Peer review**: At least 1 approval from team member
4. **Senior review**: For architectural changes, senior dev approval required
5. **Merge**: After all approvals and checks pass

---

## Development Tools

### Recommended VS Code Extensions

```json
{
  "recommendations": [
    "vue.volar",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-azuretools.vscode-docker",
    "github.copilot",
    "eamodio.gitlens"
  ]
}
```

### Code Formatting

**Frontend** (Prettier + ESLint):

```json
// .prettierrc
{
  "semi": false,
  "singleQuote": true,
  "trailingComma": "es5",
  "printWidth": 100,
  "tabWidth": 2
}
```

**Backend** (Black + isort):

```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py310']

[tool.isort]
profile = "black"
line_length = 100
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Set up hooks
pre-commit install
```

**`.pre-commit-config.yaml`**:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
```

---

## Troubleshooting

### Common Issues

**Issue**: Tests fail with "Module not found"
**Solution**: Ensure dependencies are installed: `npm install` or `pip install -r requirements.txt`

**Issue**: Docker containers won't start
**Solution**: Check logs: `docker-compose logs -f`

**Issue**: Database migration errors
**Solution**: Reset database: `docker-compose down -v && docker-compose up -d`

**Issue**: Port already in use
**Solution**: Change port in `.env` or kill process: `lsof -ti:5173 | xargs kill`

---

## Getting Help

- **Documentation**: Check `/docs` directory first
- **Team Chat**: Slack #cogstack-dev channel
- **Issues**: Create GitHub issue with template
- **Code Review**: Request review in PR comments

---

**Version**: 1.0
**Last Updated**: 2025-01-20
**Maintainer**: Development Team
