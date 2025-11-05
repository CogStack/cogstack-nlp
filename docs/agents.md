# AI Agent Development Guidelines

## Purpose

This document establishes standards and best practices for AI-assisted development on the CogStack NLP Full Potential UI project. These guidelines ensure consistent, high-quality code delivery while leveraging AI capabilities effectively.

## Core Principles

### 1. PRD-First Development

Every feature, component, or significant change MUST begin with a mini-PRD that includes:

- **Objective**: Clear statement of intended outcome
- **Inputs/Outputs**: Specific data structures expected
- **Constraints**: Performance, security, compliance, coding standards
- **Acceptance Criteria**: Measurable definition of "done"

**Location**: All PRDs stored in `/docs/prd/sprint-{N}/` directory

### 2. Incremental Development

- Work is divided into **sprints** (1-2 weeks of focused work)
- Each sprint contains 3-5 **tickets** (achievable in single session)
- No "big bang" implementations - build incrementally
- Each increment must be testable and demonstrable

### 3. Iterative Cycle (Pair Programming Model)

```
┌─────────────────────────────────────────────┐
│ 1. PROMPT                                   │
│    - Provide PRD excerpt                    │
│    - Include relevant code context          │
│    - Specify acceptance criteria            │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│ 2. GENERATE                                 │
│    - Agent drafts solution                  │
│    - Includes tests first                   │
│    - Follows coding standards               │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│ 3. REVIEW                                   │
│    - Human acts as senior developer         │
│    - Check against standards                │
│    - Identify gaps/errors                   │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│ 4. REFINE                                   │
│    - Request targeted fixes                 │
│    - No vague "make it better" requests     │
│    - Specific, actionable feedback          │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│ 5. TEST                                     │
│    - Execute tests locally                  │
│    - Provide failure feedback               │
│    - Iterate until all tests pass           │
└────────────┬────────────────────────────────┘
             │
             ▼
          COMMIT
```

## Version Control Standards

### Branching Strategy

```
main (production-ready code)
  │
  ├── develop (integration branch)
  │     │
  │     ├── feature/sprint-1-patient-search
  │     ├── feature/sprint-2-timeline-view
  │     ├── feature/sprint-3-clinical-alerts
  │     └── ...
  │
  └── hotfix/* (emergency production fixes)
```

### Commit Requirements

**MANDATORY**: Every agent-generated code change MUST be committed with this format:

```
<type>(<scope>): <short summary>

[Agent-generated code]

Changes:
- Bullet list of specific changes made
- Each change on its own line
- Be specific (e.g., "Added PatientSearchService.query() method")

Rationale:
- Why this change was made
- What problem it solves
- Any architectural decisions

Tests:
- List of tests added/modified
- Test coverage percentage (if applicable)

AI Context:
- PRD reference: docs/prd/sprint-1/patient-search.md
- Session: Sprint 1, Ticket 3
- Review status: [Pending/Approved]
```

**Commit Types**:
- `feat`: New feature
- `fix`: Bug fix
- `test`: Adding/modifying tests
- `refactor`: Code refactoring
- `docs`: Documentation
- `style`: Code formatting
- `perf`: Performance improvement
- `build`: Build system changes

### Pre-Commit Checklist

Before committing agent-generated code:

- [ ] All tests pass locally
- [ ] Code follows project style guide
- [ ] Documentation updated (if applicable)
- [ ] No sensitive data in commit
- [ ] Commit message follows format above
- [ ] Changes align with PRD acceptance criteria

## Testing Philosophy

### Test-First Development (MANDATORY)

1. **Agent writes tests FIRST**
   - Unit tests for all public methods
   - Integration tests for component interactions
   - Edge case tests for error handling

2. **Then implement to satisfy tests**
   - Code written to make tests pass
   - No implementation without corresponding test

3. **Test Coverage Requirements**
   - Minimum 80% code coverage
   - 100% coverage for critical paths (authentication, data processing)
   - All error handlers must be tested

### Test Structure

```javascript
describe('PatientSearchService', () => {
  describe('query()', () => {
    it('should return patients matching simple concept search', async () => {
      // Arrange
      const searchParams = { concept: 'atrial flutter' }

      // Act
      const results = await service.query(searchParams)

      // Assert
      expect(results).toHaveLength(47)
      expect(results[0]).toHaveProperty('mrn')
      expect(results[0]).toHaveProperty('annotations')
    })

    it('should handle no results gracefully', async () => {
      // Test edge case
    })

    it('should throw error on invalid input', async () => {
      // Test error handling
    })
  })
})
```

## Context Management

### Keep Prompts Focused

**DO**:
```
"Implement the PatientSearchService.query() method per PRD section 3.2.
Relevant context:
- API endpoint: /api/v1/patients/search
- Input schema: docs/schema/patient-search-input.json
- Expected output: docs/schema/patient-search-output.json

Current code: [paste only PatientSearchService.ts]
```

**DON'T**:
```
"Build the patient search feature" [dumps entire codebase]
```

### Maintain Design Documents

**Location**: `/docs/design/`

Keep updated:
- `architecture.md` - System architecture decisions
- `api-spec.md` - API endpoints and schemas
- `naming-conventions.md` - Variable/function naming standards
- `ui-components.md` - Reusable component library
- `database-schema.md` - Data models

Reference these in prompts to maintain consistency.

## Sprint Workflow

### Sprint Planning (Start of Sprint)

1. Review PRD for sprint
2. Break PRD into tickets (GitHub issues)
3. Create feature branch from `develop`
4. Set up testing infrastructure for sprint

### Daily Development

1. Pick ticket from sprint backlog
2. Create sub-branch if needed: `feature/sprint-1-patient-search/ticket-3`
3. Follow iterative cycle (Prompt → Generate → Review → Refine → Test)
4. Commit with proper format
5. Update ticket status

### Sprint Review (End of Sprint)

**Agent must provide**:

```markdown
# Sprint {N} Retrospective

## Deliverables
- [x] Patient Search API endpoint
- [x] Patient Search UI component
- [ ] Patient Search pagination (moved to next sprint)

## Code Quality Metrics
- Test Coverage: 87%
- Linting Errors: 0
- Type Safety: 100% (TypeScript strict mode)

## Architectural Decisions
- Chose Elasticsearch over PostgreSQL for concept search (performance)
- Implemented caching layer with Redis (200ms → 50ms response time)

## Technical Debt
- Patient Search pagination needs refactor (current implementation not scalable)
- Consider extracting search logic to separate microservice

## Risks Identified
- MedCAT API rate limiting could impact performance under load
- Need to implement request queuing

## Recommendations for Next Sprint
- Implement pagination before building Timeline View
- Add integration tests for MedCAT API client
- Consider WebSocket for real-time updates
```

## Security & Compliance

### MANDATORY Security Checks

Every agent-generated code MUST:

- [ ] **No hardcoded credentials** (use environment variables)
- [ ] **Input validation** on all user inputs
- [ ] **SQL injection prevention** (use parameterized queries)
- [ ] **XSS prevention** (escape all user-generated content)
- [ ] **CSRF protection** (tokens on all state-changing operations)
- [ ] **PHI handling** (de-identification where required)
- [ ] **Audit logging** (track who accessed what data)

### GDPR/HIPAA Compliance

When handling patient data:

```javascript
// CORRECT - De-identified for logging
logger.info('Patient search executed', {
  userId: req.user.id,
  searchTerms: sanitize(req.body.query),
  resultCount: results.length
})

// WRONG - Logging PHI
logger.info('Patient search', {
  patientName: results[0].name,  // ❌ PHI
  mrn: results[0].mrn            // ❌ PHI
})
```

## Code Quality Standards

### TypeScript/JavaScript

- **Strict mode enabled**
- **ESLint + Prettier** enforced
- **No `any` types** (use proper typing)
- **Functional programming** preferred (immutability, pure functions)
- **Error handling**: Always use try-catch, never swallow errors

```typescript
// CORRECT
async function searchPatients(query: PatientSearchQuery): Promise<Patient[]> {
  try {
    const results = await medcatClient.search(query)
    return results.map(mapToPatient)
  } catch (error) {
    logger.error('Patient search failed', { error, query })
    throw new PatientSearchError('Search failed', { cause: error })
  }
}

// WRONG
async function searchPatients(query: any): Promise<any> {
  const results = await medcatClient.search(query)  // No error handling
  return results
}
```

### Python

- **Type hints required** (PEP 484)
- **Black formatter** enforced
- **Pylint/Flake8** with no warnings
- **Docstrings** for all public functions (Google style)

```python
# CORRECT
def search_patients(
    query: PatientSearchQuery,
    filters: Optional[Dict[str, Any]] = None
) -> List[Patient]:
    """
    Search for patients using MedCAT concept extraction.

    Args:
        query: Search parameters including concept terms
        filters: Optional additional filters (temporal, meta-annotations)

    Returns:
        List of Patient objects matching search criteria

    Raises:
        PatientSearchError: If MedCAT API fails or invalid query
    """
    try:
        results = medcat_client.search(query, filters)
        return [Patient.from_dict(r) for r in results]
    except MedCATException as e:
        logger.error(f"Patient search failed: {e}")
        raise PatientSearchError("Search failed") from e
```

## Performance Requirements

### API Response Times

- **Search endpoints**: < 500ms (p95)
- **Patient timeline**: < 1000ms (p95)
- **Real-time annotations**: < 200ms (p95)

### Frontend Performance

- **Initial page load**: < 2 seconds
- **Component render**: < 100ms
- **Search results display**: < 300ms after API response

### Scalability Targets

- **Concurrent users**: 500+
- **Documents processed/hour**: 10,000+
- **Database queries**: Optimized (indexed, < 50ms)

## Documentation Requirements

### Code Documentation

Every function/method MUST have:
- Purpose description
- Parameter types and descriptions
- Return type and description
- Example usage (for public APIs)
- Error conditions

### API Documentation

- OpenAPI 3.0 spec for all endpoints
- Request/response examples
- Error code documentation
- Rate limiting information

### User Documentation

- README.md in each component directory
- Setup instructions
- Configuration options
- Troubleshooting guide

## Agent Communication Protocol

### How to Request Work

**Good Request**:
```
I need to implement the Patient Search API endpoint per PRD Sprint 1, Section 3.

Objective: Create REST endpoint that accepts concept-based search queries
Input: POST /api/v1/patients/search with PatientSearchQuery JSON
Output: PatientSearchResponse with array of Patient objects
Constraints:
- Response time < 500ms
- Input validation required
- GDPR-compliant logging
Acceptance:
- Unit tests pass (>80% coverage)
- Integration test with mock MedCAT service passes
- Returns 200 for valid query, 400 for invalid, 500 for errors

Context: [paste relevant code files]
```

**Bad Request**:
```
"Build the patient search thing"
```

### How to Provide Feedback

**Good Feedback**:
```
The error handling in PatientSearchService.query() needs improvement:

1. Line 45: Don't swallow the error - log it and re-throw
2. Line 52: Add input validation before calling MedCAT API
3. Line 67: Return type should be Promise<Patient[]> not Promise<any>

Please update these specific issues.
```

**Bad Feedback**:
```
"This code isn't good, make it better"
```

## Enforcement

### Pull Request Requirements

All PRs must:
- [ ] Reference PRD section implemented
- [ ] Include test results screenshot
- [ ] Pass all CI/CD checks (linting, tests, build)
- [ ] Have descriptive commit messages
- [ ] Be reviewed by human (agent code not auto-merged)

### Definition of Done

A ticket is "done" when:
- [ ] Code implements PRD acceptance criteria
- [ ] Tests written and passing (>80% coverage)
- [ ] Code reviewed and approved
- [ ] Documentation updated
- [ ] Deployed to staging environment
- [ ] Manually tested by human
- [ ] No critical security issues (Snyk scan clean)

---

## Quick Reference Checklist

Before marking any work complete:

```
□ PRD created/referenced
□ Tests written FIRST
□ Implementation satisfies tests
□ Commit message follows format
□ Code style compliant
□ No security issues
□ Documentation updated
□ Manually tested
□ Sprint retrospective updated (if sprint complete)
```

---

**Version**: 1.0
**Last Updated**: 2025-01-20
**Maintainer**: Development Team
