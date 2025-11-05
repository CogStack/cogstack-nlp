# PRD: Sprint 2 - Patient Timeline View

**Sprint**: 2 of 14
**Phase**: Foundation (Phase 1)
**Duration**: 2 weeks
**Priority**: P0 (Critical)
**Story Points**: 13
**Dependencies**: Sprint 1 (Patient Search)

---

## 1. Objective

Build an interactive timeline visualization that displays a patient's medical history with extracted concepts organized chronologically, including relationship visualizations between conditions, medications, and procedures.

**Success Definition**: Clinicians can view a patient's 5-year medical history as an interactive timeline that loads within 1 second and clearly shows temporal relationships between medical events.

---

## 2. User Stories

### 2.1 Chronological Concept Display

**As a** clinician
**I want to** see a patient's medical concepts displayed chronologically
**So that** I understand their disease progression and treatment timeline

**Acceptance Criteria**:
- Timeline displays concepts grouped by date (day/month/year granularity)
- Concepts color-coded by type (diagnosis=red, medication=blue, procedure=green)
- Zoom in/out to adjust time scale (day, week, month, year views)
- Scroll or pan to navigate through history
- Timeline loads within 1 second for 5-year history

**Priority**: P0

---

### 2.2 Relationship Visualization

**As a** clinician
**I want to** see relationships between conditions and treatments
**So that** I understand treatment rationale and comorbidities

**Acceptance Criteria**:
- Display relationships as connecting lines (e.g., Diabetes → Metformin)
- Relationship types: treats, causes, complication_of, contraindicates
- Hover over relationship to see type and confidence
- Click relationship to see supporting evidence from clinical notes

**Priority**: P0

---

### 2.3 Document Drill-Down

**As a** clinician
**I want to** click on timeline events to see source documents
**So that** I can verify findings in original clinical notes

**Acceptance Criteria**:
- Click concept opens modal with document text
- Concept highlighted in document
- Show all documents containing this concept
- Navigate between documents with prev/next buttons

**Priority**: P1

---

### 2.4 Concept Filtering

**As a** clinician
**I want to** filter timeline by concept type
**So that** I can focus on specific aspects (e.g., only medications)

**Acceptance Criteria**:
- Filter by concept type (diagnosis, medication, procedure, symptom, lab)
- Filter by CUI or concept name
- Filter by temporality (current, historical)
- Filters update timeline instantly (< 200ms)

**Priority**: P1

---

## 3. Functional Requirements

### 3.1 API Endpoints

#### 3.1.1 Get Patient Timeline

```
GET /api/v1/patients/{mrn}/timeline
```

**Query Parameters**:
```typescript
interface TimelineQueryParams {
  startDate?: string        // ISO 8601, default: 5 years ago
  endDate?: string          // ISO 8601, default: today
  conceptTypes?: string[]   // Filter by type
  includeConcepts?: string[] // Filter by specific CUIs
  includeRelationships?: boolean // Default: true
}
```

**Response**:

```typescript
interface TimelineResponse {
  patient: PatientInfo
  timeline: TimelineEvent[]
  relationships: Relationship[]
  dateRange: {
    start: string
    end: string
  }
  metadata: {
    totalEvents: number
    conceptTypes: { [type: string]: number }
  }
}

interface TimelineEvent {
  id: string
  date: string              // ISO 8601
  concepts: ConceptAnnotation[]
  documentId: string
  documentType: string
  eventType: 'diagnosis' | 'medication' | 'procedure' | 'symptom' | 'lab'
}

interface Relationship {
  id: string
  source: string            // CUI
  target: string            // CUI
  type: 'treats' | 'causes' | 'complication_of' | 'contraindicates'
  confidence: number        // 0.0 to 1.0
  evidence: {
    documentId: string
    excerpt: string
  }[]
}
```

---

### 3.2 Frontend Components

#### 3.2.1 PatientTimeline.vue

**Location**: `frontend/src/components/clinical/PatientTimeline.vue`

**Key Libraries**:
- D3.js or vis-timeline for timeline rendering
- D3.js for relationship graphs

**Features**:
- Horizontal timeline with zoomable date axis
- Concept cards positioned at event dates
- Relationship lines connecting related concepts
- Mini-map for navigation overview
- Tooltip on hover showing concept details

**State**:
```typescript
interface TimelineState {
  events: TimelineEvent[]
  relationships: Relationship[]
  filters: {
    conceptTypes: string[]
    dateRange: [Date, Date]
  }
  zoom: number
  selectedConcept: string | null
  viewMode: 'timeline' | 'network'
}
```

---

#### 3.2.2 RelationshipGraph.vue

**Location**: `frontend/src/components/clinical/RelationshipGraph.vue`

**Features**:
- Force-directed graph of concept relationships
- Node size indicates concept frequency
- Edge thickness indicates relationship strength
- Color-coded by concept type
- Click node to filter timeline to that concept

---

### 3.3 Backend Services

#### 3.3.1 TimelineService

**Location**: `backend/app/services/timeline_service.py`

**Methods**:

```python
class TimelineService:
    async def get_patient_timeline(
        self,
        mrn: str,
        start_date: date,
        end_date: date,
        filters: TimelineFilters,
        user: User
    ) -> TimelineResponse:
        """
        Build patient timeline from annotations.

        Process:
        1. Query Elasticsearch for patient's annotations in date range
        2. Group annotations by document date
        3. Extract relationships using RelCAT (if available)
        4. Sort events chronologically
        5. Return structured timeline

        Args:
            mrn: Patient medical record number
            start_date: Timeline start
            end_date: Timeline end
            filters: Concept type and other filters
            user: For audit logging

        Returns:
            TimelineResponse with events and relationships
        """

    async def get_concept_relationships(
        self,
        mrn: str,
        cuis: List[str]
    ) -> List[Relationship]:
        """
        Extract relationships between specified concepts.

        Uses RelCAT if available, otherwise infers from
        co-occurrence patterns.
        """
```

---

## 4. Non-Functional Requirements

### 4.1 Performance

- **Timeline Load**: < 1 second for 5-year history
- **Filter Application**: < 200ms
- **Zoom/Pan**: 60 FPS (smooth animations)
- **Document Load**: < 300ms

**Optimization**:
- Virtualization (only render visible timeline portion)
- Lazy load documents on demand
- Cache timeline data (10-minute TTL)

---

### 4.2 Usability

- **Responsive**: Works on desktop and tablets (min 768px width)
- **Accessibility**: Keyboard navigation, screen reader support
- **Color Blind Friendly**: Use patterns in addition to colors
- **Loading States**: Show skeleton loaders during data fetch

---

## 5. Acceptance Criteria

- [ ] Timeline displays patient's medical history chronologically
- [ ] Concepts grouped by document date
- [ ] Color-coded by concept type
- [ ] Relationships visualized as connecting lines
- [ ] Timeline loads within 1 second
- [ ] Zoom and pan work smoothly (60 FPS)
- [ ] Click concept opens document modal
- [ ] Filter by concept type updates instantly
- [ ] Test coverage ≥ 85%
- [ ] Works on Chrome, Firefox, Safari, Edge

---

## 6. Testing Strategy

**Unit Tests**:
```typescript
describe('TimelineService', () => {
  it('should group events by date', async () => {
    const events = await service.getTimeline('MRN123')
    expect(events).toHaveLength(45)
    expect(events[0].date).toBe('2024-01-15')
  })

  it('should extract relationships', async () => {
    const relationships = await service.getRelationships('MRN123')
    expect(relationships).toContainEqual({
      source: 'C0011849', // Diabetes
      target: 'C0025598', // Metformin
      type: 'treats'
    })
  })
})
```

**E2E Tests**:
```typescript
test('timeline interaction', async ({ page }) => {
  await page.goto('/patients/MRN123/timeline')

  // Verify timeline renders
  await expect(page.locator('[data-testid="timeline"]')).toBeVisible()

  // Click concept
  await page.click('[data-testid="concept-C0011849"]')

  // Verify document modal opens
  await expect(page.locator('[data-testid="document-modal"]')).toBeVisible()
})
```

---

## 7. Dependencies

- **Sprint 1**: Patient search (provides patient selection)
- **RelCAT**: Relationship extraction model (optional, can infer from co-occurrence)
- **D3.js**: Timeline visualization library

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| D3.js complexity | Use existing timeline library (vis-timeline) |
| Performance with large timelines (10+ years) | Implement virtualization, paginate by year |
| RelCAT not available | Infer relationships from temporal co-occurrence |

---

**PRD Version**: 1.0
**Last Updated**: 2025-01-20
