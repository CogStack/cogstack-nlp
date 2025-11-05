# PRD: Sprint 6 - Concept Analytics Dashboard (Research)

**Sprint**: 6 of 14
**Phase**: Research & Analytics (Phase 2)
**Duration**: 2 weeks
**Priority**: P1 (High)
**Story Points**: 13
**Dependencies**: Sprint 5 (Cohort Builder)

---

## 1. Objective

Provide population-level analytics on medical concepts including prevalence trends, comorbidity networks, treatment patterns, and outcome correlations to support epidemiological research and quality improvement.

**Success Definition**: Researchers can analyze disease prevalence trends over time, visualize comorbidity networks, and identify treatment patterns with dashboard loading within 3 seconds.

---

## 2. User Stories

### 2.1 Concept Prevalence Trends

**As a** researcher
**I want** to see disease prevalence trends over time
**So that** I can identify public health patterns

**Acceptance Criteria**:
- Line chart showing monthly/yearly prevalence for selected concept
- Compare multiple concepts on same chart
- Filter by demographics (age, gender, department)
- Export chart data to CSV
- Dashboard loads within 3 seconds

**Priority**: P0

---

### 2.2 Comorbidity Network

**As a** researcher
**I want** to visualize disease comorbidity networks
**So that** I understand which conditions co-occur

**Acceptance Criteria**:
- Network graph with concepts as nodes
- Edge thickness indicates co-occurrence frequency
- Node size indicates prevalence
- Interactive: click node to highlight connections
- Filter by minimum co-occurrence threshold

**Priority**: P0

---

### 2.3 Treatment Pathway Analysis

**As a** quality officer
**I want** to analyze common treatment sequences
**So that** I identify care patterns and variations

**Acceptance Criteria**:
- Sankey diagram showing condition → treatment → outcome flows
- Display most common pathways
- Time-to-treatment metrics
- Compare across departments or time periods

**Priority**: P1

---

## 3. Functional Requirements

### 3.1 API Endpoints

#### 3.1.1 Get Concept Prevalence Trends

```
GET /api/v1/analytics/concepts/{cui}/prevalence
```

**Query Parameters**:
```typescript
interface PrevalenceQueryParams {
  startDate: string            // ISO 8601
  endDate: string              // ISO 8601
  granularity: 'day' | 'week' | 'month' | 'year'
  filters?: {
    ageRange?: [number, number]
    gender?: string
    department?: string
  }
}
```

**Response**:
```typescript
interface PrevalenceResponse {
  concept: {
    cui: string
    name: string
  }
  data: {
    date: string
    prevalence: number         // cases per 1000 patients
    count: number              // absolute count
    denominator: number        // total patients
  }[]
  statistics: {
    mean: number
    median: number
    trend: 'increasing' | 'decreasing' | 'stable'
    changePercent: number      // % change over period
  }
}
```

---

#### 3.1.2 Get Comorbidity Network

```
GET /api/v1/analytics/concepts/{cui}/comorbidities
```

**Response**:
```typescript
interface ComorbidityResponse {
  concept: {
    cui: string
    name: string
  }
  comorbidities: {
    cui: string
    name: string
    cooccurrenceCount: number
    relativeRisk: number       // RR vs general population
    confidence: number         // Statistical significance
  }[]
  network: {
    nodes: {
      id: string               // CUI
      label: string            // Concept name
      size: number             // Prevalence
      type: string             // Concept type
    }[]
    edges: {
      source: string           // CUI
      target: string           // CUI
      weight: number           // Co-occurrence frequency
    }[]
  }
}
```

---

#### 3.1.3 Get Treatment Pathways

```
GET /api/v1/analytics/pathways
```

**Query Parameters**:
```typescript
interface PathwayQueryParams {
  condition: string            // CUI
  startDate: string
  endDate: string
  minPathwayFrequency?: number // Default: 5
}
```

**Response**:
```typescript
interface PathwayResponse {
  pathways: {
    id: string
    sequence: {
      type: 'diagnosis' | 'medication' | 'procedure'
      concept: string          // CUI
      name: string
    }[]
    patientCount: number
    avgTimeToNextStep: number  // days
    outcomeMetrics?: {
      readmissionRate: number
      mortalityRate: number
    }
  }[]
}
```

---

### 3.2 Frontend Components

#### 3.2.1 ConceptAnalytics.vue

**Location**: `frontend/src/components/research/ConceptAnalytics.vue`

**Features**:
- Concept search autocomplete
- Tabbed interface (Trends, Comorbidities, Pathways, Outcomes)
- Date range selector
- Filter panel (demographics)
- Export buttons

---

#### 3.2.2 PrevalenceTrendChart.vue

**Technology**: Plotly.js or Chart.js

**Features**:
- Time series line chart
- Multiple series support (compare concepts)
- Zoom/pan capabilities
- Tooltip with details
- Export as PNG/SVG

---

#### 3.2.3 ComorbidityNetwork.vue

**Technology**: D3.js force-directed graph

**Features**:
- Interactive network graph
- Node coloring by concept type
- Edge thickness by co-occurrence
- Hover for details
- Click to filter/expand

---

#### 3.2.4 TreatmentPathwayChart.vue

**Technology**: D3.js Sankey diagram

**Features**:
- Flow visualization condition → treatment → outcome
- Pathway thickness by frequency
- Hover for patient counts
- Click pathway to see patient list

---

## 4. Non-Functional Requirements

### 4.1 Performance

- **Dashboard Load**: < 3 seconds
- **Chart Rendering**: < 1 second
- **Data Aggregation**: Pre-compute daily (batch job)
- **Cache**: 24-hour TTL for analytics

---

### 4.2 Scalability

- **Support**: 100,000+ patients
- **Concepts**: 10,000+ concepts
- **Time Range**: 10+ years of data

---

## 5. Acceptance Criteria

- [ ] Prevalence trends chart displays monthly data
- [ ] Comorbidity network visualizes relationships
- [ ] Treatment pathways show common sequences
- [ ] Dashboard loads within 3 seconds
- [ ] Filters update charts within 1 second
- [ ] Export to CSV/PNG functional
- [ ] Test coverage ≥ 85%

---

## 6. Testing Strategy

**Unit Tests**:
```python
# test_analytics_service.py
async def test_prevalence_calculation():
    """Test prevalence calculation."""
    prevalence = await analytics.get_prevalence(
        cui="C0011849",  # Diabetes
        start_date="2023-01-01",
        end_date="2023-12-31",
        granularity="month"
    )

    assert len(prevalence.data) == 12  # 12 months
    assert all(d.prevalence >= 0 for d in prevalence.data)
```

---

## 7. Dependencies

- **Historical Data**: 2+ years for meaningful trends
- **Structured Data**: Lab results, vitals for outcome correlations (optional)

---

**PRD Version**: 1.0
**Last Updated**: 2025-01-20
