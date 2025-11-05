# PRD: Sprint 3 - Real-Time Clinical Decision Support

**Sprint**: 3 of 14
**Phase**: Foundation (Phase 1)
**Duration**: 2 weeks
**Priority**: P0 (Critical)
**Story Points**: 21
**Dependencies**: Sprint 1, Sprint 2

---

## 1. Objective

Provide real-time clinical decision support by automatically annotating clinical documents as they're written, generating alerts for critical conditions, suggesting clinical pathways, and identifying quality gaps.

**Success Definition**: Clinical documents are annotated within 200ms of submission, with relevant alerts displayed immediately to clinicians with <5% false positive rate.

---

## 2. User Stories

### 2.1 Real-Time Document Annotation

**As a** clinician
**I want** documents annotated as I write them
**So that** I receive immediate feedback and alerts

**Acceptance Criteria**:
- Document annotated within 200ms of save/submission
- Annotations displayed inline with highlighting
- Confidence scores shown for each concept
- Allow manual correction of annotations

**Priority**: P0

---

### 2.2 Clinical Alerts

**As a** clinician
**I want** to receive alerts for critical conditions
**So that** I don't miss important clinical findings

**Acceptance Criteria**:
- Alert triggers based on configurable rules (e.g., sepsis criteria)
- Severity levels: Critical (red), High (orange), Medium (yellow), Low (blue)
- Alert displays with recommended actions
- Alert dismissal tracked with reason
- Alerts persist in patient record

**Priority**: P0

---

### 2.3 Clinical Pathway Suggestions

**As a** clinician
**I want** pathway suggestions based on documented conditions
**So that** I follow evidence-based care protocols

**Acceptance Criteria**:
- Suggest pathways when conditions detected (e.g., "ACS pathway" for MI)
- Show pathway criteria and next steps
- One-click pathway activation
- Track pathway compliance

**Priority**: P1

---

### 2.4 Quality Gap Identification

**As a** quality officer
**I want** to identify missing documentation or interventions
**So that** we maintain quality standards

**Acceptance Criteria**:
- Detect missing elements (e.g., "Diabetes mentioned but no HbA1c documented")
- Alert for overdue screenings
- Suggest clinical codes
- Track gap closure

**Priority**: P1

---

## 3. Functional Requirements

### 3.1 API Endpoints

#### 3.1.1 Annotate Document (Real-Time)

```
POST /api/v1/documents/annotate
```

**Input**:
```typescript
interface AnnotationRequest {
  documentId?: string        // Optional, for existing docs
  text: string               // Document text
  documentType: string       // "progress_note", "discharge_summary", etc.
  patientMrn: string        // For context-aware alerts
  metadata?: {
    department: string
    provider: string
    timestamp: string
  }
}
```

**Output**:
```typescript
interface AnnotationResponse {
  documentId: string
  annotations: Annotation[]
  alerts: Alert[]
  suggestions: Suggestion[]
  processingTime: number     // milliseconds
}

interface Alert {
  id: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  type: 'clinical' | 'quality' | 'safety'
  title: string
  message: string
  triggeredBy: string[]      // CUIs that triggered alert
  recommendations: Action[]
  dismissible: boolean
  requiresAcknowledgment: boolean
}

interface Action {
  label: string
  type: 'order' | 'pathway' | 'consult' | 'documentation'
  payload: any
}

interface Suggestion {
  type: 'pathway' | 'coding' | 'documentation'
  title: string
  description: string
  confidence: number
  action: Action
}
```

---

#### 3.1.2 Dismiss Alert

```
POST /api/v1/alerts/{alertId}/dismiss
```

**Input**:
```typescript
interface DismissAlertRequest {
  reason: string
  overrideReason?: string    // If dismissing critical alert
}
```

---

#### 3.1.3 Get Alert Rules

```
GET /api/v1/alerts/rules
```

**Output**: List of configured alert rules with enable/disable status

---

### 3.2 Alert Rules Engine

#### 3.2.1 Rule Configuration

**Location**: `backend/app/config/alert_rules.yaml`

**Example Rules**:

```yaml
rules:
  - id: sepsis-screening
    name: "Sepsis Screening Required"
    severity: critical
    enabled: true
    conditions:
      - concept: C0243026  # Sepsis
        confidence: >= 0.7
        temporality: current
    actions:
      - type: alert
        message: "Sepsis identified - initiate sepsis bundle within 1 hour"
        recommendations:
          - "Start broad-spectrum antibiotics"
          - "Obtain blood cultures"
          - "Administer IV fluids"
          - "Measure lactate"

  - id: aki-drug-review
    name: "AKI - Review Nephrotoxic Drugs"
    severity: high
    enabled: true
    conditions:
      - concept: C0022660  # Acute Kidney Injury
        AND
      - medication_class: nephrotoxic
    actions:
      - type: alert
        message: "AKI detected with nephrotoxic medication - review and adjust doses"

  - id: diabetes-foot-exam
    name: "Diabetic Foot Exam Overdue"
    severity: medium
    enabled: true
    conditions:
      - concept: C0011849  # Diabetes
        AND
      - foot_exam_date: > 365 days ago OR null
    actions:
      - type: suggestion
        message: "Annual diabetic foot exam overdue"
        action:
          type: order
          order_code: FOOT_EXAM

  - id: anticoagulation-afib
    name: "AFib Without Anticoagulation"
    severity: high
    enabled: true
    conditions:
      - concept: C0004238  # Atrial Fibrillation
        AND
      - medication_class: anticoagulant
        exists: false
        AND
      - CHADS2VASc: >= 2
    actions:
      - type: alert
        message: "Atrial fibrillation with CHADS2VASc ≥2 but no anticoagulation documented"
        recommendations:
          - "Consider anticoagulation therapy"
          - "Document contraindications if applicable"
```

---

### 3.3 WebSocket Integration (Optional for Phase 1)

**For real-time updates as clinician types**:

```typescript
// Client connects
const ws = new WebSocket('ws://api/v1/documents/annotate/stream')

// Send text chunks as user types (debounced)
ws.send(JSON.stringify({
  documentId: 'DOC123',
  text: 'Patient presents with chest pain...',
  partial: true  // Indicates incomplete document
}))

// Receive annotations in real-time
ws.onmessage = (event) => {
  const { annotations, alerts } = JSON.parse(event.data)
  // Update UI with annotations and alerts
}
```

---

### 3.4 Frontend Components

#### 3.4.1 DocumentAnnotator.vue

**Location**: `frontend/src/components/clinical/DocumentAnnotator.vue`

**Features**:
- Text editor with real-time annotation highlighting
- Inline concept badges with confidence scores
- Alert panel showing active alerts
- Suggestion panel with recommended actions

---

#### 3.4.2 AlertPanel.vue

**Location**: `frontend/src/components/clinical/AlertPanel.vue`

**Features**:
- List of active alerts sorted by severity
- Alert cards with expand/collapse
- Dismiss button with reason input
- Acknowledge button for critical alerts
- Alert history view

---

#### 3.4.3 SuggestionPanel.vue

**Location**: `frontend/src/components/clinical/SuggestionPanel.vue`

**Features**:
- Clinical pathway suggestions
- ICD-10 code suggestions
- Documentation completeness checks
- One-click actions

---

## 4. Non-Functional Requirements

### 4.1 Performance

- **Annotation Time**: < 200ms (p95)
- **Alert Display**: Immediate (< 50ms after annotation)
- **WebSocket Latency**: < 100ms (if implemented)
- **Load**: Support 100 concurrent users annotating

---

### 4.2 Reliability

- **Alert Accuracy**: < 5% false positive rate (validated against clinician feedback)
- **Uptime**: 99.9% (alerts are safety-critical)
- **Failover**: If MedCAT down, queue documents for processing when service returns

---

### 4.3 Security

- **Alert Audit**: Log all alerts (triggered, dismissed, acknowledged)
- **Override Approval**: Critical alert dismissal requires supervisor approval (configurable)
- **PHI Protection**: No PHI in alert logs

---

## 5. Acceptance Criteria

- [ ] Document annotated within 200ms of submission
- [ ] Alerts generated based on configured rules
- [ ] Alerts display with severity levels and recommendations
- [ ] Alerts can be dismissed with reason
- [ ] Clinical pathway suggestions shown when criteria met
- [ ] Quality gaps identified (missing documentation)
- [ ] Alert audit log complete and queryable
- [ ] False positive rate < 5% (validated with 100 test cases)
- [ ] Test coverage ≥ 85%

---

## 6. Testing Strategy

**Unit Tests**:

```python
# test_alert_rules_engine.py
def test_sepsis_alert_triggered():
    """Test sepsis alert fires when sepsis detected."""
    annotations = [
        Annotation(cui="C0243026", confidence=0.9, temporality="current")
    ]

    alerts = alert_engine.evaluate_rules(annotations)

    assert len(alerts) == 1
    assert alerts[0].severity == "critical"
    assert alerts[0].type == "sepsis-screening"

def test_no_alert_when_negated():
    """Test alert doesn't fire for negated findings."""
    annotations = [
        Annotation(cui="C0243026", confidence=0.9, negated=True)
    ]

    alerts = alert_engine.evaluate_rules(annotations)

    assert len(alerts) == 0
```

**Integration Tests**:

```python
# test_real_time_annotation_api.py
async def test_annotation_endpoint():
    """Test real-time annotation endpoint."""
    payload = {
        "text": "Patient with severe sepsis and hypotension.",
        "documentType": "progress_note",
        "patientMrn": "MRN123"
    }

    response = await client.post("/api/v1/documents/annotate", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "annotations" in data
    assert "alerts" in data
    assert len(data["alerts"]) >= 1  # Sepsis alert
    assert data["processingTime"] < 200
```

---

## 7. Dependencies

- **MedCAT Service**: Must be low-latency (<200ms)
- **Alert Rules**: Clinical input required to configure rules
- **GPU Acceleration**: Recommended for low-latency processing

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Alert fatigue from false positives | Tune confidence thresholds, allow per-user customization |
| 200ms latency target not achievable | GPU acceleration, caching, async processing |
| Alert rules too complex | Start with 5-10 simple rules, iterate based on feedback |
| Clinician resistance to alerts | Involve clinicians in rule design, allow dismissal |

---

**PRD Version**: 1.0
**Last Updated**: 2025-01-20
