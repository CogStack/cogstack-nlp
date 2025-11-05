# PRD: Sprint 9 - Quality Dashboard (Governance)

**Sprint**: 9 of 14
**Phase**: Governance & Quality (Phase 3)
**Duration**: 2 weeks
**Priority**: P1 (High)
**Story Points**: 13
**Dependencies**: Sprint 1, Sprint 3 (Clinical Alerts foundation)

---

## 1. Objective

Build a real-time quality metrics dashboard that tracks clinical quality measures, identifies gaps in care, monitors compliance with clinical guidelines, and enables department/provider performance comparison.

**Success Definition**: Quality officers can track 10+ configurable quality metrics in real-time, identify patients with care gaps, and generate compliance reports within 5 minutes.

---

## 2. User Stories

### 2.1 Quality Metrics Tracking

**As a** quality officer
**I want** to track clinical quality metrics in real-time
**So that** I ensure compliance with quality standards

**Acceptance Criteria**:
- Display 10+ configurable quality metrics (e.g., sepsis bundles, VTE prophylaxis)
- Show current compliance percentage vs target
- Color-coded indicators (green ≥ target, yellow within 5%, red < target)
- Trend charts showing performance over time
- Dashboard updates within 5 minutes of new data

**Priority**: P0

---

### 2.2 Care Gap Identification

**As a** quality officer
**I want** to identify patients with quality gaps
**So that** I can intervene before adverse outcomes

**Acceptance Criteria**:
- List patients missing required interventions
- Drill-down to patient-level details
- Alert care teams of gaps
- Track gap closure over time
- Export gap lists for follow-up

**Priority**: P0

---

### 2.3 Department Performance Comparison

**As a** department head
**I want** to compare my department's performance
**So that** I identify improvement opportunities

**Acceptance Criteria**:
- Compare departments side-by-side
- Benchmarking against hospital average
- Statistical significance indicators
- Filter by metric and time period
- Export comparison reports

**Priority**: P1

---

### 2.4 Automated Compliance Reports

**As a** compliance officer
**I want** automated monthly compliance reports
**So that** I demonstrate regulatory compliance

**Acceptance Criteria**:
- Generate PDF reports with all metrics
- Include trend charts and gap lists
- Schedule automated generation (monthly/quarterly)
- Email reports to stakeholders
- Archive reports for audit

**Priority**: P1

---

## 3. Functional Requirements

### 3.1 Quality Metric Definitions

**Configuration**: `backend/app/config/quality_metrics.yaml`

**Example Metrics**:

```yaml
metrics:
  - id: sepsis-bundle-compliance
    name: "Sepsis Bundle Compliance (1-hour)"
    category: "Safety"
    target: 0.95
    description: "Percentage of sepsis patients receiving bundle within 1 hour"
    calculation:
      numerator:
        - concept: C0243026  # Sepsis
          AND
        - all_interventions_within:
            timeframe: 60 minutes
            interventions:
              - "Blood cultures obtained"
              - "Antibiotics administered"
              - "Lactate measured"
              - "IV fluids started"
      denominator:
        - concept: C0243026  # Sepsis patients

  - id: vte-prophylaxis
    name: "VTE Prophylaxis (Surgical)"
    category: "Safety"
    target: 0.90
    numerator:
      - procedure: surgical
        AND
      - medication_class: anticoagulant OR mechanical_prophylaxis
        within: 24 hours
    denominator:
      - procedure: surgical
        AND
      - vte_risk: high

  - id: diabetic-foot-exam
    name: "Annual Diabetic Foot Exam"
    category: "Preventive"
    target: 0.85
    numerator:
      - concept: C0011849  # Diabetes
        AND
      - procedure: FOOT_EXAM
        within: 365 days
    denominator:
      - concept: C0011849  # Diabetes

  - id: aki-documentation
    name: "AKI Stage Documentation"
    category: "Documentation"
    target: 0.95
    numerator:
      - concept: C0022660  # AKI
        AND
      - documented_stage: 1|2|3
    denominator:
      - concept: C0022660  # AKI
```

---

### 3.2 API Endpoints

#### 3.2.1 Get Quality Metrics Dashboard

```
GET /api/v1/quality/metrics/dashboard
```

**Query Parameters**:
```typescript
interface DashboardQueryParams {
  startDate: string
  endDate: string
  department?: string
  provider?: string
}
```

**Response**:
```typescript
interface QualityDashboardResponse {
  summary: {
    totalMetrics: number
    metricsAboveTarget: number
    metricsBelowTarget: number
    overallScore: number       // 0-100
  }
  metrics: QualityMetric[]
  trends: {
    [metricId: string]: {
      date: string
      value: number
    }[]
  }
}

interface QualityMetric {
  id: string
  name: string
  category: string
  currentValue: number         // 0.0 to 1.0
  target: number               // 0.0 to 1.0
  status: 'above' | 'near' | 'below'
  numerator: number
  denominator: number
  trend: 'improving' | 'stable' | 'declining'
  changePercent: number        // vs previous period
}
```

---

#### 3.2.2 Get Care Gaps

```
GET /api/v1/quality/metrics/{metricId}/gaps
```

**Response**:
```typescript
interface CareGapsResponse {
  metric: QualityMetric
  gaps: {
    patientMrn: string
    demographics: {
      age: number
      gender: string
      department: string
    }
    gapDetails: {
      missingIntervention: string
      dueDate: string
      daysPastDue: number
    }
    assignedProvider: string
    priority: 'high' | 'medium' | 'low'
  }[]
  totalGaps: number
}
```

---

#### 3.2.3 Generate Compliance Report

```
POST /api/v1/quality/reports/generate
```

**Input**:
```typescript
interface ReportRequest {
  reportType: 'monthly' | 'quarterly' | 'annual'
  period: {
    start: string
    end: string
  }
  metrics?: string[]           // Default: all metrics
  departments?: string[]       // Default: all departments
  format: 'pdf' | 'xlsx'
}
```

**Response**: Download link to generated report

---

### 3.3 Frontend Components

#### 3.3.1 QualityDashboard.vue

**Location**: `frontend/src/components/governance/QualityDashboard.vue`

**UI Sketch**:

```
┌─────────────────────────────────────────────────────────┐
│  Quality Metrics Dashboard - January 2024              │
├─────────────────────────────────────────────────────────┤
│  Overall Performance: 87% (Target: 90%)                │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ✓ Above Target: 7   ⚠ Near Target: 2  ✗ Below: 1│  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  SAFETY METRICS                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Sepsis Bundle Compliance                         │  │
│  │ ▓▓▓▓▓▓▓▓▓▓ 92% ✓ Target: 95%  ↗ +3%            │  │
│  │ 184/200 patients                                │  │
│  │ [View Gaps (16)] [Trend Chart]                  │  │
│  ├──────────────────────────────────────────────────┤  │
│  │ VTE Prophylaxis                                  │  │
│  │ ▓▓▓▓▓▓▓▓▓  87% ⚠ Target: 90%  ↘ -2%            │  │
│  │ 261/300 patients                                │  │
│  │ [View Gaps (39)] [Trend Chart]                  │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  PREVENTIVE METRICS                                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Diabetic Foot Exam (Annual)                      │  │
│  │ ▓▓▓▓▓▓▓    78% ✗ Target: 85%  → 0%              │  │
│  │ 390/500 patients                                │  │
│  │ [View Gaps (110)] [Alert Teams]                 │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  [Export Report] [Configure Metrics] [Schedule]        │
└─────────────────────────────────────────────────────────┘
```

---

#### 3.3.2 MetricCard.vue

**Features**:
- Metric name and category
- Current value vs target
- Progress bar with color coding
- Trend indicator (improving/stable/declining)
- Quick actions (view gaps, view trend)

---

#### 3.3.3 CareGapsTable.vue

**Features**:
- Sortable table of patients with gaps
- Filter by department, provider, priority
- Bulk actions (send alerts, export)
- Mark gap as closed

---

#### 3.3.4 DepartmentComparison.vue

**Features**:
- Bar chart comparing departments
- Statistical significance indicators
- Drill-down to department details
- Export comparison data

---

## 4. Non-Functional Requirements

### 4.1 Performance

- **Dashboard Load**: < 3 seconds
- **Metric Calculation**: Real-time (5-minute refresh)
- **Gap List**: < 2 seconds
- **Report Generation**: < 30 seconds

**Optimization**:
- Pre-calculate metrics (batch job every 5 minutes)
- Cache dashboard data (5-minute TTL)
- Asynchronous report generation

---

### 4.2 Reliability

- **Data Accuracy**: 99%+ (validated against manual review)
- **Uptime**: 99.9% (quality monitoring is critical)
- **Audit Trail**: All metric calculations logged

---

## 5. Acceptance Criteria

- [ ] Dashboard displays 10+ configurable quality metrics
- [ ] Metrics show current value vs target with color coding
- [ ] Trend charts show performance over time
- [ ] Gap lists identify patients missing interventions
- [ ] Department comparison functional
- [ ] Automated reports generate and email on schedule
- [ ] Dashboard loads within 3 seconds
- [ ] Test coverage ≥ 85%

---

## 6. Testing Strategy

**Unit Tests**:

```python
# test_quality_metrics.py
async def test_sepsis_bundle_calculation():
    """Test sepsis bundle compliance calculation."""
    metric = await quality_service.calculate_metric(
        metric_id="sepsis-bundle-compliance",
        start_date="2024-01-01",
        end_date="2024-01-31"
    )

    assert metric.numerator == 184
    assert metric.denominator == 200
    assert metric.currentValue == 0.92
    assert metric.status == "below"  # 92% < 95% target

async def test_gap_identification():
    """Test care gap identification."""
    gaps = await quality_service.get_care_gaps(
        metric_id="diabetic-foot-exam"
    )

    assert len(gaps.gaps) == 110
    assert all(g.daysPastDue >= 0 for g in gaps.gaps)
```

**Integration Tests**:

```python
# test_quality_dashboard_api.py
async def test_dashboard_endpoint():
    """Test quality dashboard API."""
    response = await client.get(
        "/api/v1/quality/metrics/dashboard",
        params={"startDate": "2024-01-01", "endDate": "2024-01-31"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert len(data["metrics"]) >= 10
```

---

## 7. Dependencies

- **Clinical Guidelines**: Quality metric definitions from clinical team
- **Structured Data**: Some metrics require lab results, medication orders
- **Alert System**: From Sprint 3 (to notify providers of gaps)

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Metric calculation complexity | Start with simple metrics, iterate |
| Data quality issues | Manual validation of sample, feedback loop |
| Provider alert fatigue | Prioritize gaps, allow customization |
| Report generation timeout | Asynchronous processing, email when ready |

---

**PRD Version**: 1.0
**Last Updated**: 2025-01-20
