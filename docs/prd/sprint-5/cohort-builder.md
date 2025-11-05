# PRD: Sprint 5 - Cohort Builder (Research Workbench)

**Sprint**: 5 of 14
**Phase**: Research & Analytics (Phase 2)
**Duration**: 3 weeks
**Priority**: P1 (High)
**Story Points**: 21
**Dependencies**: Sprint 1 (Patient Search foundation)

---

## 1. Objective

Enable researchers to identify patient cohorts using complex concept-based inclusion/exclusion criteria with temporal logic, real-time patient count estimation, and de-identified data export capabilities.

**Success Definition**: Researchers can build cohorts with complex criteria (AND/OR logic, temporal operators) and see patient counts update within 1 second, with ability to export de-identified datasets for analysis.

---

## 2. User Stories

### 2.1 Visual Query Builder

**As a** researcher
**I want** a visual interface to build cohort selection criteria
**So that** I can create complex queries without writing code

**Acceptance Criteria**:
- Drag-and-drop interface for adding criteria
- Support AND/OR logic between criteria groups
- Visual grouping of related criteria
- Save/load cohort definitions
- Share cohort definitions with team

**Priority**: P0

---

### 2.2 Temporal Logic

**As a** researcher
**I want** to specify temporal relationships between conditions
**So that** I can find patients with specific disease progression patterns

**Acceptance Criteria**:
- Temporal operators: BEFORE, AFTER, WITHIN, DURING
- Example: "Diabetes diagnosed BEFORE heart failure"
- Example: "MI occurred WITHIN 30 days AFTER stent placement"
- Support date ranges and relative time periods

**Priority**: P0

---

### 2.3 Real-Time Patient Count

**As a** researcher
**I want** to see patient counts update as I add criteria
**So that** I can assess cohort feasibility in real-time

**Acceptance Criteria**:
- Patient count updates within 1 second of criteria change
- Show counts for each individual criterion
- Show final cohort size after all criteria applied
- Display demographics breakdown (age, gender, ethnicity)

**Priority**: P0

---

### 2.4 De-Identified Export

**As a** researcher
**I want** to export de-identified patient data
**So that** I comply with IRB and privacy requirements

**Acceptance Criteria**:
- Export formats: CSV, XLSX, JSON
- Automatic PHI removal (names, dates, MRNs replaced with pseudonyms)
- Customizable column selection
- Include annotations and document excerpts (de-identified)
- Audit log of all exports (who, when, what)

**Priority**: P0

---

## 3. Functional Requirements

### 3.1 API Endpoints

#### 3.1.1 Build Cohort Query

```
POST /api/v1/cohorts/build
```

**Input**:
```typescript
interface CohortQuery {
  name: string
  description?: string
  criteria: CriteriaGroup
}

interface CriteriaGroup {
  operator: 'AND' | 'OR'
  criteria: (Criterion | CriteriaGroup)[]
}

interface Criterion {
  type: 'concept' | 'demographic' | 'temporal'
  config: ConceptCriterion | DemographicCriterion | TemporalCriterion
}

interface ConceptCriterion {
  concept: string              // CUI or concept name
  operator: 'HAS' | 'NOT_HAS'
  filters?: {
    temporality?: 'current' | 'historical' | 'all'
    includeNegated?: boolean
    includeFamily?: boolean
  }
}

interface DemographicCriterion {
  field: 'age' | 'gender' | 'ethnicity' | 'department'
  operator: '=' | '!=' | '>' | '<' | '>=' | '<=' | 'IN' | 'NOT_IN'
  value: any
}

interface TemporalCriterion {
  eventA: string               // Concept CUI
  relation: 'BEFORE' | 'AFTER' | 'WITHIN' | 'DURING'
  eventB: string               // Concept CUI or date
  timeframe?: {
    value: number
    unit: 'days' | 'weeks' | 'months' | 'years'
  }
}
```

**Example Request**:

```json
{
  "name": "COPD Medication Adherence Study",
  "criteria": {
    "operator": "AND",
    "criteria": [
      {
        "type": "concept",
        "config": {
          "concept": "C0024117",  // COPD
          "operator": "HAS",
          "filters": {
            "temporality": "current"
          }
        }
      },
      {
        "type": "concept",
        "config": {
          "concept": "C0001927",  // Bronchodilator
          "operator": "HAS"
        }
      },
      {
        "type": "demographic",
        "config": {
          "field": "age",
          "operator": ">=",
          "value": 40
        }
      },
      {
        "type": "demographic",
        "config": {
          "field": "age",
          "operator": "<=",
          "value": 80
        }
      },
      {
        "operator": "OR",
        "criteria": [
          {
            "type": "concept",
            "config": {
              "concept": "C0037369",  // Smoking
              "operator": "HAS"
            }
          },
          {
            "type": "concept",
            "config": {
              "concept": "C0015952",  // Former smoker
              "operator": "HAS"
            }
          }
        ]
      }
    ]
  }
}
```

**Output**:

```typescript
interface CohortResponse {
  cohortId: string
  query: CohortQuery
  results: {
    patientCount: number
    demographics: {
      ageDistribution: { [ageGroup: string]: number }
      genderDistribution: { [gender: string]: number }
      ethnicityDistribution: { [ethnicity: string]: number }
    }
    criteriaBreakdown: {
      [criterionId: string]: {
        description: string
        matchCount: number
      }
    }
  }
  buildTime: number            // milliseconds
  estimatedExportSize: number  // MB
}
```

---

#### 3.1.2 Export Cohort Data

```
POST /api/v1/cohorts/{cohortId}/export
```

**Input**:

```typescript
interface ExportRequest {
  format: 'csv' | 'xlsx' | 'json'
  columns?: string[]           // Default: all available
  includeAnnotations?: boolean // Default: true
  includeDocuments?: boolean   // Default: false (text snippets only)
  deidentify?: boolean         // Default: true
}
```

**Output**: Download link to de-identified dataset

**De-Identification Process**:
1. Replace MRNs with pseudonymous IDs (MRN123 → PATIENT_001)
2. Shift dates by random offset (-365 to +365 days, consistent per patient)
3. Remove names, addresses, phone numbers (via AnonCAT)
4. Generalize ages >89 to "90+"
5. Suppress small cell sizes (<5 patients in subgroup)

---

#### 3.1.3 Save/Load Cohort Definition

```
POST /api/v1/cohorts/save
GET /api/v1/cohorts/{cohortId}
GET /api/v1/cohorts/my-cohorts
DELETE /api/v1/cohorts/{cohortId}
```

---

### 3.2 Frontend Components

#### 3.2.1 CohortBuilder.vue

**Location**: `frontend/src/components/research/CohortBuilder.vue`

**Features**:
- Drag-and-drop query builder
- Criteria panels with add/remove
- AND/OR logic selector
- Real-time patient count display
- Demographics charts (age distribution, gender breakdown)
- Save/load cohort definitions
- Export button with format selector

**UI Sketch**:

```
┌─────────────────────────────────────────────────────────┐
│  Cohort Builder: COPD Medication Adherence Study        │
├─────────────────────────────────────────────────────────┤
│  INCLUSION CRITERIA (AND)                    47 patients │
│  ┌──────────────────────────────────────────────────┐  │
│  │ ✓ Diagnosis: COPD (current)              1,247   │  │
│  │ ✓ Prescribed: Bronchodilator               980   │  │
│  │ ✓ Age: 40-80 years                         756   │  │
│  │ ✓ Smoking history (current or former)      654   │  │
│  │ [+ Add Criterion]                                │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  EXCLUSION CRITERIA (OR)                      12 excluded│
│  ┌──────────────────────────────────────────────────┐  │
│  │ ✓ Diagnosis: Asthma                          8    │  │
│  │ ✓ Diagnosis: Lung cancer                     4    │  │
│  │ [+ Add Criterion]                                │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  DEMOGRAPHICS SUMMARY                                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Age: [Chart: 40-50: 12, 50-60: 18, 60-70: 15]   │  │
│  │ Gender: Male: 28 (59%), Female: 19 (41%)        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  [Save Cohort] [Export Data ▼] [Share] [Clear]         │
└─────────────────────────────────────────────────────────┘
```

---

#### 3.2.2 CriterionEditor.vue

**Location**: `frontend/src/components/research/CriterionEditor.vue`

**Features**:
- Concept search autocomplete
- Temporal operator selector
- Date picker for temporal criteria
- Demographic field selector
- Remove criterion button

---

## 4. Non-Functional Requirements

### 4.1 Performance

- **Patient Count Update**: < 1 second per criteria change
- **Cohort Build**: < 3 seconds for 100K patient database
- **Export Generation**: < 30 seconds for 1000 patients
- **De-Identification**: < 5 seconds for 1000 documents

---

### 4.2 Privacy & Compliance

- **De-Identification Accuracy**: >99% PHI removal (validated)
- **Audit Trail**: Complete export audit log
- **Cell Suppression**: Groups <5 patients suppressed in exports
- **IRB Compliance**: Export includes IRB approval metadata

---

## 5. Acceptance Criteria

- [ ] Visual query builder supports AND/OR logic
- [ ] Temporal operators (BEFORE, AFTER, WITHIN) functional
- [ ] Patient count updates within 1 second
- [ ] Demographics breakdown displayed
- [ ] Cohort definitions can be saved and loaded
- [ ] Export generates de-identified CSV/XLSX/JSON
- [ ] De-identification removes >99% of PHI (validated on test set)
- [ ] All exports audited (user, timestamp, cohort)
- [ ] Test coverage ≥ 85%

---

## 6. Testing Strategy

**Unit Tests**:

```python
# test_cohort_builder.py
async def test_simple_cohort():
    """Test simple cohort with single criterion."""
    query = CohortQuery(
        criteria=CriteriaGroup(
            operator="AND",
            criteria=[
                Criterion(
                    type="concept",
                    config=ConceptCriterion(concept="C0011849")  # Diabetes
                )
            ]
        )
    )

    result = await cohort_service.build_cohort(query)

    assert result.patientCount == 1247
    assert result.buildTime < 3000

async def test_temporal_logic():
    """Test temporal criteria."""
    query = CohortQuery(
        criteria=CriteriaGroup(
            operator="AND",
            criteria=[
                Criterion(
                    type="temporal",
                    config=TemporalCriterion(
                        eventA="C0011849",  # Diabetes
                        relation="BEFORE",
                        eventB="C0018801",  # Heart failure
                        timeframe={"value": 1, "unit": "years"}
                    )
                )
            ]
        )
    )

    result = await cohort_service.build_cohort(query)

    assert result.patientCount > 0
    # Verify temporal logic applied correctly
```

**De-Identification Tests**:

```python
# test_deidentification.py
def test_phi_removal():
    """Test PHI is removed from export."""
    data = [
        {"mrn": "MRN123", "name": "John Smith", "dob": "1980-01-15"},
        {"mrn": "MRN456", "name": "Jane Doe", "dob": "1975-05-20"}
    ]

    deidentified = deidentifier.process(data)

    # Check no PHI present
    for row in deidentified:
        assert "MRN" not in str(row)
        assert "John" not in str(row)
        assert "Smith" not in str(row)
        # Check pseudonymous ID present
        assert "PATIENT_" in row["pseudonym_id"]
```

---

## 7. Dependencies

- **Sprint 1**: Patient search foundation
- **AnonCAT Service**: For de-identification
- **Elasticsearch**: For fast cohort queries
- **IRB**: Approval process for data export

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Complex queries too slow | Pre-compute common cohorts, optimize Elasticsearch queries |
| De-identification misses PHI | Comprehensive testing, manual review of samples |
| Researcher learning curve | Interactive tutorial, example cohorts, documentation |

---

**PRD Version**: 1.0
**Last Updated**: 2025-01-20
