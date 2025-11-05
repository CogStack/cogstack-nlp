# PRD: Sprint 1 - Patient Search & Discovery

**Sprint**: 1 of 14
**Phase**: Foundation (Phase 1)
**Duration**: 2 weeks
**Priority**: P0 (Critical)
**Story Points**: 13

---

## 1. Objective

Build core patient search capability that enables clinicians to find patients based on medical concepts extracted from clinical notes using MedCAT NLP. The search must support concept-based queries, temporal filtering, and meta-annotation filtering (negation, experiencer, temporality).

**Success Definition**: Clinicians can find relevant patients within 500ms by searching for medical conditions/concepts, with accurate filtering for current vs historical conditions.

---

## 2. Background & Context

### Problem Statement

Currently, finding patients with specific medical conditions requires:
- Manual chart review (time-consuming, error-prone)
- Reliance on structured data codes (incomplete, often outdated)
- No ability to search free-text clinical notes

This leads to:
- Missed patients for clinical pathways
- Inability to identify cohorts for quality improvement
- Delayed identification of safety issues

### Solution

Leverage MedCAT's NLP capabilities to:
1. Extract medical concepts from clinical notes
2. Enable search across unstructured clinical text
3. Filter by temporal context (current vs historical)
4. Distinguish patient vs family history

### Business Value

- **Time Savings**: Reduce patient identification time from hours to seconds
- **Quality Improvement**: Identify all relevant patients, not just coded ones
- **Clinical Pathways**: Enable automated pathway enrollment
- **Research**: Foundation for cohort building

---

## 3. User Stories

### 3.1 Core Search Functionality

**As a** clinician
**I want to** search for patients by medical condition/concept
**So that** I can quickly identify relevant patients for review

**Acceptance Criteria**:
- Given I enter "atrial flutter" in search box
- When I click Search
- Then I see list of patients with that concept in their notes
- And results appear within 500ms
- And each result shows patient demographics + concept highlights

**Priority**: P0

---

### 3.2 Temporal Filtering

**As a** clinician
**I want to** filter by current vs historical conditions
**So that** I find patients with active conditions only

**Acceptance Criteria**:
- Given search results for "diabetes"
- When I apply filter "Current conditions only"
- Then I see only patients with recent/ongoing diabetes mentions
- And historical/resolved diabetes is excluded
- And filter updates results within 200ms

**Priority**: P0

---

### 3.3 Meta-Annotation Filtering

**As a** clinician
**I want to** exclude family history and negated conditions
**So that** I find patients with actual diagnoses

**Acceptance Criteria**:
- Given search for "myocardial infarction"
- When I check "Exclude family history"
- Then I see only patients where MI refers to patient (not relatives)
- And when I check "Exclude negated"
- Then "No history of MI" mentions are excluded

**Priority**: P0

---

### 3.4 Document Context

**As a** clinician
**I want to** see which documents contain the concepts
**So that** I can verify findings in original context

**Acceptance Criteria**:
- Given patient in search results
- When I click on concept tag (e.g., "atrial flutter")
- Then I see list of documents containing that concept
- And clicking document shows full text with concept highlighted
- And highlight includes character position in text

**Priority**: P1

---

### 3.5 Advanced Filters

**As a** clinician
**I want to** filter by date range, department, and provider
**So that** I narrow results to relevant scope

**Acceptance Criteria**:
- Filter by date range (e.g., "Last 30 days", "Last year", custom range)
- Filter by department (e.g., "Cardiology", "Emergency")
- Filter by document type (e.g., "Discharge summary", "Progress notes")
- Multiple filters combine with AND logic
- Clear all filters button resets to all results

**Priority**: P2

---

## 4. Functional Requirements

### 4.1 Search Input

**Input Schema**:

```typescript
interface PatientSearchQuery {
  concept: string                    // Required: Medical concept to search
  filters?: {
    temporal?: 'current' | 'historical' | 'all'  // Default: 'all'
    includeNegated?: boolean         // Default: false
    includeFamily?: boolean          // Default: false
    dateRange?: {
      start: string                  // ISO 8601 date
      end: string                    // ISO 8601 date
    }
    departments?: string[]           // Department IDs
    documentTypes?: string[]         // Document type IDs
  }
  pagination?: {
    page: number                     // Default: 1
    pageSize: number                 // Default: 20, max: 100
  }
  sort?: 'relevance' | 'date' | 'name'  // Default: 'relevance'
}
```

**Validation Rules**:
- `concept` is required, minimum 3 characters
- `concept` maximum 100 characters
- `dateRange.start` must be before `dateRange.end`
- `pagination.pageSize` between 1 and 100
- Invalid input returns 400 Bad Request with error details

---

### 4.2 Search Output

**Output Schema**:

```typescript
interface PatientSearchResponse {
  results: Patient[]
  pagination: {
    page: number
    pageSize: number
    totalResults: number
    totalPages: number
  }
  performance: {
    searchTime: number              // milliseconds
    source: 'cache' | 'live'        // indicate if cached
  }
  filters: AppliedFilters           // Echo applied filters
}

interface Patient {
  mrn: string                       // Medical Record Number (de-identified in logs)
  demographics: {
    age: number
    gender: string
    department: string
  }
  annotations: Annotation[]         // Matching concepts from MedCAT
  lastUpdated: string               // ISO 8601 timestamp
}

interface Annotation {
  cui: string                       // Concept Unique Identifier
  conceptName: string               // Human-readable name
  sourceValue: string               // Actual text in document
  documentId: string
  documentType: string
  documentDate: string
  startChar: number                 // Character position in document
  endChar: number
  confidence: number                // 0.0 to 1.0
  metaAnnotations: {
    temporality?: 'current' | 'historical' | 'future'
    negated?: boolean
    experiencer?: 'patient' | 'family' | 'other'
    certainty?: 'definite' | 'probable' | 'possible'
  }
  snomedCT?: string[]               // SNOMED-CT codes
  icd10?: string[]                  // ICD-10 codes
}
```

---

### 4.3 API Endpoints

#### 4.3.1 Search Patients

```
POST /api/v1/patients/search
```

**Request Headers**:
```
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

**Request Body**: See `PatientSearchQuery` schema

**Response**: See `PatientSearchResponse` schema

**Status Codes**:
- `200 OK`: Search successful
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Missing/invalid auth token
- `403 Forbidden`: User lacks permission
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: MedCAT service down

**Example Request**:

```json
POST /api/v1/patients/search
{
  "concept": "atrial flutter",
  "filters": {
    "temporal": "current",
    "includeNegated": false,
    "includeFamily": false,
    "dateRange": {
      "start": "2024-01-01",
      "end": "2024-01-31"
    }
  },
  "pagination": {
    "page": 1,
    "pageSize": 20
  },
  "sort": "relevance"
}
```

**Example Response**:

```json
{
  "results": [
    {
      "mrn": "MRN123456",
      "demographics": {
        "age": 72,
        "gender": "Male",
        "department": "Cardiology"
      },
      "annotations": [
        {
          "cui": "C0004239",
          "conceptName": "Atrial Flutter",
          "sourceValue": "atrial flutter",
          "documentId": "DOC789",
          "documentType": "Progress Note",
          "documentDate": "2024-01-15T10:30:00Z",
          "startChar": 145,
          "endChar": 160,
          "confidence": 0.95,
          "metaAnnotations": {
            "temporality": "current",
            "negated": false,
            "experiencer": "patient",
            "certainty": "definite"
          },
          "snomedCT": ["5370000"],
          "icd10": ["I48.92"]
        }
      ],
      "lastUpdated": "2024-01-15T10:35:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalResults": 47,
    "totalPages": 3
  },
  "performance": {
    "searchTime": 245,
    "source": "live"
  },
  "filters": {
    "temporal": "current",
    "includeNegated": false,
    "includeFamily": false,
    "dateRange": {
      "start": "2024-01-01",
      "end": "2024-01-31"
    }
  }
}
```

---

#### 4.3.2 Get Patient Details

```
GET /api/v1/patients/{mrn}
```

**Purpose**: Retrieve full patient information with all annotations

**Response**: Single `Patient` object with full annotation history

---

#### 4.3.3 Get Document with Highlights

```
GET /api/v1/documents/{documentId}?highlightCUI={cui}
```

**Purpose**: Retrieve document text with specific concept highlighted

**Response**:

```typescript
interface DocumentResponse {
  documentId: string
  text: string
  highlights: {
    startChar: number
    endChar: number
    cui: string
    conceptName: string
  }[]
  metadata: {
    documentType: string
    author: string
    date: string
    department: string
  }
}
```

---

### 4.4 Frontend Components

#### 4.4.1 PatientSearch.vue

**Location**: `frontend/src/components/clinical/PatientSearch.vue`

**Responsibilities**:
- Search input field with autocomplete (suggest recent searches)
- Filter panel (temporal, negation, family history, date range)
- Search button with loading state
- Display search results in table/card view
- Pagination controls

**Props**:
```typescript
interface Props {
  initialQuery?: string
  defaultFilters?: Partial<SearchFilters>
}
```

**Events**:
```typescript
interface Emits {
  'patient-selected': (mrn: string) => void
  'search-completed': (results: PatientSearchResponse) => void
}
```

**State Management**:
- Use Pinia store: `usePatientSearchStore()`
- Store recent searches (localStorage)
- Cache search results (5 minute TTL)

---

#### 4.4.2 PatientList.vue

**Location**: `frontend/src/components/clinical/PatientList.vue`

**Responsibilities**:
- Display patient cards/rows with demographics
- Show matching concepts with badges
- Click to view patient details
- Highlight matching terms

**Props**:
```typescript
interface Props {
  patients: Patient[]
  loading: boolean
  highlightConcept?: string
}
```

---

#### 4.4.3 FilterPanel.vue

**Location**: `frontend/src/components/clinical/FilterPanel.vue`

**Responsibilities**:
- Temporal filter (radio buttons: All / Current / Historical)
- Checkboxes (Include negated, Include family history)
- Date range picker
- Department multi-select
- Document type multi-select
- Clear filters button

---

### 4.5 Backend Services

#### 4.5.1 PatientSearchService

**Location**: `backend/app/services/patient_search_service.py`

**Responsibilities**:
- Receive search query from API endpoint
- Call MedCAT service to find matching concepts
- Query Elasticsearch for patients with matching annotations
- Apply filters (temporal, negation, family, date)
- Sort and paginate results
- Return formatted response

**Methods**:

```python
class PatientSearchService:
    async def search(
        self,
        query: PatientSearchQuery,
        user: User
    ) -> PatientSearchResponse:
        """
        Execute patient search with concept-based filters.

        Args:
            query: Search parameters
            user: Authenticated user (for audit logging)

        Returns:
            PatientSearchResponse with matching patients

        Raises:
            PatientSearchError: If search fails
            MedCATServiceError: If MedCAT service unavailable
        """

    async def get_patient_details(
        self,
        mrn: str,
        user: User
    ) -> Patient:
        """Get full patient details with all annotations."""

    async def get_document(
        self,
        document_id: str,
        highlight_cui: Optional[str],
        user: User
    ) -> DocumentResponse:
        """Retrieve document with optional concept highlighting."""
```

---

#### 4.5.2 MedCATClient

**Location**: `backend/app/clients/medcat/medcat_client.py`

**Responsibilities**:
- HTTP client for MedCAT service
- Concept normalization (search term → CUIs)
- Error handling and retries
- Response parsing

**Methods**:

```python
class MedCATClient:
    async def get_concepts_for_term(
        self,
        term: str
    ) -> List[Concept]:
        """
        Resolve search term to medical concepts (CUIs).

        Args:
            term: Medical term (e.g., "atrial flutter")

        Returns:
            List of matching concepts with CUIs

        Example:
            >>> await client.get_concepts_for_term("MI")
            [
                Concept(cui="C0027051", name="Myocardial Infarction"),
                Concept(cui="C0340280", name="Myocardial Ischemia")
            ]
        """

    async def annotate_text(
        self,
        text: str
    ) -> List[Annotation]:
        """Annotate clinical text with MedCAT."""
```

---

#### 4.5.3 ElasticsearchService

**Location**: `backend/app/services/elasticsearch_service.py`

**Responsibilities**:
- Build Elasticsearch query from search parameters
- Execute query against patient index
- Parse Elasticsearch response
- Handle aggregations (for counts, facets)

**Index Schema**:

```json
{
  "mappings": {
    "properties": {
      "mrn": { "type": "keyword" },
      "demographics": {
        "properties": {
          "age": { "type": "integer" },
          "gender": { "type": "keyword" },
          "department": { "type": "keyword" }
        }
      },
      "annotations": {
        "type": "nested",
        "properties": {
          "cui": { "type": "keyword" },
          "conceptName": { "type": "text" },
          "sourceValue": { "type": "text" },
          "documentId": { "type": "keyword" },
          "documentType": { "type": "keyword" },
          "documentDate": { "type": "date" },
          "startChar": { "type": "integer" },
          "endChar": { "type": "integer" },
          "confidence": { "type": "float" },
          "metaAnnotations": {
            "properties": {
              "temporality": { "type": "keyword" },
              "negated": { "type": "boolean" },
              "experiencer": { "type": "keyword" },
              "certainty": { "type": "keyword" }
            }
          },
          "snomedCT": { "type": "keyword" },
          "icd10": { "type": "keyword" }
        }
      },
      "lastUpdated": { "type": "date" }
    }
  }
}
```

**Query Example**:

```python
async def build_search_query(
    self,
    cuis: List[str],
    filters: SearchFilters
) -> dict:
    """Build Elasticsearch query."""
    query = {
        "query": {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "annotations",
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "terms": {
                                                "annotations.cui": cuis
                                            }
                                        }
                                    ],
                                    "filter": []
                                }
                            }
                        }
                    }
                ]
            }
        }
    }

    # Add temporal filter
    if filters.temporal == "current":
        query["query"]["bool"]["must"][0]["nested"]["query"]["bool"]["filter"].append({
            "term": {
                "annotations.metaAnnotations.temporality": "current"
            }
        })

    # Add negation filter
    if not filters.includeNegated:
        query["query"]["bool"]["must"][0]["nested"]["query"]["bool"]["must"].append({
            "term": {
                "annotations.metaAnnotations.negated": False
            }
        })

    # Add family history filter
    if not filters.includeFamily:
        query["query"]["bool"]["must"][0]["nested"]["query"]["bool"]["must"].append({
            "term": {
                "annotations.metaAnnotations.experiencer": "patient"
            }
        })

    # Add date range filter
    if filters.dateRange:
        query["query"]["bool"]["filter"].append({
            "range": {
                "annotations.documentDate": {
                    "gte": filters.dateRange.start,
                    "lte": filters.dateRange.end
                }
            }
        })

    return query
```

---

## 5. Non-Functional Requirements

### 5.1 Performance

**Search Response Time**:
- **Target**: < 500ms (p95)
- **Acceptable**: < 1000ms (p95)
- **Unacceptable**: > 2000ms

**Optimization Strategies**:
- Redis caching (5-minute TTL for identical queries)
- Elasticsearch query optimization (indexes, filters vs queries)
- Pagination (max 100 results per page)
- Debounce search input (500ms delay)

**Load Requirements**:
- Support 100 concurrent users
- 1000 searches per hour
- Elasticsearch cluster: 3 nodes minimum

---

### 5.2 Security

**Authentication**:
- JWT tokens required for all API calls
- Token expiry: 1 hour
- Refresh token expiry: 7 days

**Authorization**:
- Role-based access control (RBAC)
- Roles: `clinician`, `researcher`, `admin`
- Audit log all patient searches (user, timestamp, query)

**Data Protection**:
- **NO PHI in logs**: Log query parameters but not patient identifiers
- **Input validation**: Prevent SQL injection, XSS
- **Rate limiting**: 100 requests per minute per user

**Audit Logging**:

```python
# Log format
{
    "event": "patient_search",
    "timestamp": "2024-01-20T10:30:00Z",
    "user": {
        "id": "user123",
        "username": "john.smith@hospital.nhs.uk",
        "role": "clinician"
    },
    "query": {
        "concept": "atrial flutter",
        "filters": {
            "temporal": "current"
        }
    },
    "results": {
        "count": 47,
        "searchTime": 245
    },
    "ip": "10.0.1.45"
}
```

---

### 5.3 Reliability

**Uptime**: 99.9% (excluding planned maintenance)

**Error Handling**:
- MedCAT service failure: Return cached results if available, else error
- Elasticsearch failure: Return error with retry suggestion
- Partial results: If some data unavailable, return what's available with warning

**Fallback Behavior**:
```python
try:
    # Primary: Get concepts from MedCAT
    concepts = await medcat_client.get_concepts(term)
except MedCATServiceError:
    # Fallback: Use cached concept mappings
    concepts = await cache.get_concepts(term)
    if not concepts:
        raise PatientSearchError("MedCAT service unavailable and no cached data")
```

---

### 5.4 Scalability

**Data Volume**:
- 100,000+ patients
- 10,000,000+ documents
- 100,000,000+ annotations

**Horizontal Scaling**:
- Stateless API (can add more instances)
- Elasticsearch sharding (based on patient ID)
- Redis cluster for caching

**Future Growth**:
- Design supports multi-site deployment
- Partition by hospital/trust
- Geographic data residency support

---

## 6. Acceptance Criteria

### 6.1 Functional Acceptance

- [ ] **Search by concept**: Enter "atrial flutter", get relevant patients
- [ ] **Temporal filter**: "Current only" excludes historical mentions
- [ ] **Negation filter**: "Exclude negated" removes "No history of X"
- [ ] **Family history filter**: Excludes "Mother has diabetes"
- [ ] **Date range filter**: Only results from specified date range
- [ ] **Pagination**: Navigate through results (20 per page)
- [ ] **Sorting**: Sort by relevance, date, or name
- [ ] **Document view**: Click concept to see source document
- [ ] **Highlighting**: Concept highlighted in document text

### 6.2 Non-Functional Acceptance

- [ ] **Performance**: 95% of searches complete within 500ms
- [ ] **Load**: Supports 100 concurrent users without degradation
- [ ] **Security**: All searches require authentication
- [ ] **Audit**: All searches logged with user + timestamp
- [ ] **Error handling**: Graceful failures with user-friendly messages
- [ ] **Caching**: Identical queries return cached results

### 6.3 Testing Acceptance

- [ ] **Unit tests**: 85%+ coverage for all services
- [ ] **Integration tests**: API endpoints tested with mock MedCAT
- [ ] **E2E tests**: Full search workflow tested in browser
- [ ] **Performance tests**: Load test with 100 concurrent users
- [ ] **Security tests**: Penetration testing passed

---

## 7. Testing Strategy

### 7.1 Unit Tests

**Frontend** (`frontend/tests/unit/`):

```typescript
// services/PatientSearchService.test.ts
describe('PatientSearchService', () => {
  describe('search()', () => {
    it('should search patients by concept', async () => {
      // Arrange
      const service = new PatientSearchService()
      const query = { concept: 'atrial flutter' }

      // Act
      const results = await service.search(query)

      // Assert
      expect(results.patients).toHaveLength(47)
      expect(results.performance.searchTime).toBeLessThan(500)
    })

    it('should apply temporal filter', async () => {
      // Test temporal filter
    })

    it('should handle empty results', async () => {
      // Test no results case
    })

    it('should handle API errors gracefully', async () => {
      // Test error handling
    })
  })
})

// components/PatientSearch.test.ts
describe('PatientSearch Component', () => {
  it('should display search results', async () => {
    // Component test
  })

  it('should apply filters when changed', async () => {
    // Filter interaction test
  })
})
```

**Backend** (`backend/tests/unit/`):

```python
# test_patient_search_service.py
class TestPatientSearchService:
    async def test_search_by_concept(self):
        """Test basic concept search."""
        service = PatientSearchService()
        query = PatientSearchQuery(concept="atrial flutter")

        results = await service.search(query)

        assert len(results.results) == 47
        assert results.performance.searchTime < 500

    async def test_temporal_filter(self):
        """Test temporal filtering."""
        service = PatientSearchService()
        query = PatientSearchQuery(
            concept="diabetes",
            filters=SearchFilters(temporal="current")
        )

        results = await service.search(query)

        # All results should have temporality=current
        for patient in results.results:
            for annotation in patient.annotations:
                assert annotation.metaAnnotations.temporality == "current"
```

**Target Coverage**: 85%+

---

### 7.2 Integration Tests

**API Tests** (`backend/tests/integration/`):

```python
# test_patient_search_api.py
from fastapi.testclient import TestClient

def test_patient_search_endpoint():
    """Test full search endpoint."""
    client = TestClient(app)

    # Arrange
    payload = {
        "concept": "atrial flutter",
        "filters": {
            "temporal": "current",
            "includeNegated": False
        }
    }

    # Act
    response = client.post(
        "/api/v1/patients/search",
        json=payload,
        headers={"Authorization": f"Bearer {test_token}"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 47
    assert data["performance"]["searchTime"] < 500

def test_search_without_auth():
    """Test authentication requirement."""
    client = TestClient(app)

    response = client.post(
        "/api/v1/patients/search",
        json={"concept": "test"}
    )

    assert response.status_code == 401
```

---

### 7.3 End-to-End Tests

**Playwright Tests** (`frontend/tests/e2e/`):

```typescript
// patient-search.spec.ts
import { test, expect } from '@playwright/test'

test('complete patient search workflow', async ({ page }) => {
  // Login
  await page.goto('http://localhost:5173/login')
  await page.fill('[data-testid="username"]', 'testuser')
  await page.fill('[data-testid="password"]', 'password123')
  await page.click('[data-testid="login-btn"]')

  // Navigate to search
  await page.click('[data-testid="clinical-dashboard"]')

  // Perform search
  await page.fill('[data-testid="search-input"]', 'atrial flutter')
  await page.click('[data-testid="search-btn"]')

  // Verify results
  await expect(page.locator('[data-testid="result-count"]'))
    .toContainText('47 patients found')

  // Apply filter
  await page.click('[data-testid="filter-temporal-current"]')
  await expect(page.locator('[data-testid="result-count"]'))
    .toContainText('32 patients found')

  // View patient details
  await page.click('[data-testid="patient-0"]')
  await expect(page.locator('[data-testid="patient-demographics"]'))
    .toBeVisible()
})
```

---

### 7.4 Performance Tests

**Load Test** (Apache JMeter or Locust):

```python
# locustfile.py
from locust import HttpUser, task, between

class PatientSearchUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Login and get token."""
        response = self.client.post("/api/v1/auth/login", json={
            "username": "loadtest",
            "password": "password"
        })
        self.token = response.json()["accessToken"]

    @task(10)
    def search_common_concept(self):
        """Search for common concept."""
        self.client.post(
            "/api/v1/patients/search",
            json={"concept": "diabetes"},
            headers={"Authorization": f"Bearer {self.token}"}
        )

    @task(5)
    def search_with_filters(self):
        """Search with temporal filter."""
        self.client.post(
            "/api/v1/patients/search",
            json={
                "concept": "diabetes",
                "filters": {"temporal": "current"}
            },
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

**Load Test Targets**:
- 100 concurrent users
- 1000 requests total
- 95% of requests < 500ms
- 0% error rate

---

## 8. Dependencies

### 8.1 External Services

**MedCAT Service**:
- **Required**: Yes (critical path)
- **Version**: >= 2.0
- **Endpoint**: `http://medcat-service:5000/api/process`
- **Performance**: < 200ms per document
- **Fallback**: Cached concept mappings (read-only, no new annotations)

**Elasticsearch**:
- **Required**: Yes (critical path)
- **Version**: >= 8.0
- **Cluster**: 3 nodes minimum
- **Index**: `patients` with mapping defined
- **Fallback**: None (service unavailable if ES down)

**PostgreSQL**:
- **Required**: Yes (for user auth, audit logs)
- **Version**: >= 14
- **Tables**: `users`, `audit_logs`

**Redis**:
- **Required**: No (nice to have)
- **Purpose**: Caching search results
- **Fallback**: Direct database queries (slower)

---

### 8.2 Data Requirements

**Patient Data**:
- **Minimum**: 1,000 patients for testing
- **Ideal**: 10,000+ patients for realistic testing
- **Format**: Elasticsearch index with schema defined above
- **Annotations**: Pre-processed with MedCAT (CUIs, meta-annotations)

**Test Data**:
- Known concept-patient mappings for validation
- Edge cases: negated, family history, historical
- Performance test data: Large result sets (1000+ patients)

---

### 8.3 Infrastructure

**Development Environment**:
- Docker Compose with all services
- Sample data loaded
- MedCAT model downloaded

**Staging Environment**:
- Production-like infrastructure
- Anonymized patient data
- Performance testing capability

---

## 9. Risks & Mitigation

### 9.1 High-Risk Items

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| MedCAT service performance insufficient | High | Medium | Implement aggressive caching, async processing, consider GPU acceleration |
| Elasticsearch query performance poor | High | Medium | Index optimization, query profiling, consider dedicated cluster |
| Concept search ambiguity (e.g., "MI" = multiple concepts) | Medium | High | Show all matching concepts, allow user selection, improve autocomplete |
| Security vulnerability in search (PHI exposure) | Critical | Low | Comprehensive security review, penetration testing, audit all logs |
| False positives/negatives in concept matching | Medium | High | Display confidence scores, allow user feedback, model retraining |

---

### 9.2 Assumptions

- MedCAT service is available and performant (< 200ms per doc)
- Patient documents already indexed in Elasticsearch
- Meta-annotations (temporality, negation, experiencer) already computed
- Test environment mirrors production infrastructure
- User roles and permissions already defined

---

## 10. Success Metrics

### 10.1 Launch Criteria

**Must Have (P0)**:
- [ ] Search by concept functional and tested
- [ ] Temporal filter works correctly
- [ ] Response time < 500ms (p95)
- [ ] Authentication required and working
- [ ] Audit logging implemented
- [ ] 85%+ test coverage
- [ ] Security review passed

**Should Have (P1)**:
- [ ] Document view with highlighting
- [ ] Advanced filters (date, department)
- [ ] Pagination functional
- [ ] Caching implemented

**Nice to Have (P2)**:
- [ ] Autocomplete for search input
- [ ] Recent searches saved
- [ ] Export results to CSV

---

### 10.2 Post-Launch Metrics

**Usage**:
- Track searches per day
- Track average search time
- Track filter usage (which filters most common)

**Quality**:
- Track search result clicks (are results relevant?)
- Track "zero results" searches (failed searches)
- Track user feedback (thumbs up/down on results)

**Performance**:
- Monitor API response times (p50, p95, p99)
- Monitor error rates
- Monitor cache hit rates

---

## 11. Open Questions

1. **Q**: What should happen when MedCAT service is down?
   **A**: Return cached results with warning banner. If no cache, show error with retry button.

2. **Q**: How should we handle concept ambiguity (e.g., "MI" matches multiple concepts)?
   **A**: Show all matching concepts with radio buttons, allow user to select specific CUI.

3. **Q**: Should we support wildcard/fuzzy search (e.g., "diabet*" matches "diabetes", "diabetic")?
   **A**: Yes, implement in Phase 2 (Sprint 5).

4. **Q**: How long should search results be cached?
   **A**: 5 minutes for identical queries (trade-off between freshness and performance).

5. **Q**: Should we show patient names in search results?
   **A**: Yes, but audit all access. For research users, show only de-identified MRN.

---

## 12. Appendices

### A. Wireframes

See `/docs/design/wireframes/sprint-1/` for:
- `patient-search-empty.png` - Initial search screen
- `patient-search-results.png` - Search results view
- `patient-search-filters.png` - Filter panel expanded
- `patient-details.png` - Patient detail modal

### B. API Contract

Full OpenAPI spec: `/docs/api/openapi.yaml` (Sprint 1 section)

### C. Database Schema

Elasticsearch mapping: See section 4.5.3 above

PostgreSQL tables:
```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    query_params JSONB,
    result_count INTEGER,
    search_time_ms INTEGER,
    ip_address VARCHAR(45)
);

CREATE INDEX idx_audit_logs_user_timestamp ON audit_logs(user_id, timestamp);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
```

---

**PRD Version**: 1.0
**Author**: Development Team
**Last Updated**: 2025-01-20
**Reviewers**: [Pending]
**Approval Status**: Draft
