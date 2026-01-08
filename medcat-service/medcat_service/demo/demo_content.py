
short_example = "John had been diagnosed with acute Kidney Failure the week before"


long_example = """Description: Intracerebral hemorrhage (very acute clinical changes occurred immediately).
CC: Left hand numbness on presentation; then developed lethargy later that day.

HX: On the day of presentation, this 72 y/o RHM suddenly developed generalized weakness and lightheadedness, and could not rise from a chair. Four hours later he experienced sudden left hand numbness lasting two hours. There were no other associated symptoms except for the generalized weakness and lightheadedness. He denied vertigo.

He had been experiencing falling spells without associated LOC up to several times a month for the past year.

MEDS: procardia SR, Lasix, Ecotrin, KCL, Digoxin, Colace, Coumadin.

PMH: 1)8/92 evaluation for presyncope (Echocardiogram showed: AV fibrosis/calcification, AV stenosis/insufficiency, MV stenosis with annular calcification and regurgitation, moderate TR, Decreased LV systolic function, severe LAE. MRI brain: focal areas of increased T2 signal in the left cerebellum and in the brainstem probably representing microvascular ischemic disease. IVG (MUGA scan)revealed: global hypokinesis of the LV and biventricular dysfunction, RV ejection Fx 45% and LV ejection Fx 39%. He was subsequently placed on coumadin severe valvular heart disease), 2)HTN, 3)Rheumatic fever and heart disease, 4)COPD, 5)ETOH abuse, 6)colonic polyps, 7)CAD, 8)CHF, 9)Appendectomy, 10)Junctional tachycardia.
"""  # noqa: E501

article_footer = """
## Disclaimer
This software is intended solely for the testing purposes and non-commercial use. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.

contact@cogstack.com for more information.

Please note this is a limited version of MedCAT and it is not trained or validated by clinicans.
"""  # noqa: E501

anoncat_example = """Patient Information:

Name: John Parkinson
Date of Birth: February 12, 1958
Gender: Male
Address: 789 Wellness Lane, Healthville, HV 56789
Phone: (555) 555-1234
Email: john.parkinson@email.com
Emergency Contact:

Name: Mary Parkinson
Relationship: Spouse
Phone: (555) 555-5678
Insurance Information:

Insurance Provider: HealthWell Assurance
Policy Number: HW765432109
Group Number: G876543
Medical History:

Allergies:

None reported
Medications:

Levodopa/Carbidopa for Parkinson's disease symptoms
Pramipexole for restless legs syndrome
Lisinopril for hypertension
Atorvastatin for hyperlipidemia
Metformin for Type 2 Diabetes
Medical Conditions:

Parkinson's Disease (diagnosed on June 20, 2015)
Hypertension
Hyperlipidemia
Type 2 Diabetes
Osteoarthritis
Vital Signs:

Blood Pressure: 130/80 mmHg
Heart Rate: 72 bpm
Temperature: 98.4°F
Respiratory Rate: 18 breaths per minute
Recent Inpatient Stay (Dates: September 1-10, 2023):

Reason for Admission: Acute exacerbation of Parkinson's symptoms, pneumonia, and uncontrolled diabetes.

Interventions:

Neurology Consultation for Parkinson's disease management adjustments.
Antibiotic therapy for pneumonia.
Continuous glucose monitoring and insulin therapy for diabetes control.
Physical therapy sessions to maintain mobility.
Complications:

Delirium managed with close monitoring and appropriate interventions.
Discharge Plan:

Medication adjustments for Parkinson's disease.
Follow-up appointments with neurologist, endocrinologist, and primary care.
Home health care for continued physical therapy.
Follow-up Visits:

Date: October 15, 2023

Reason for Visit: Post-discharge Follow-up
Notes: Stable Parkinson's symptoms, pneumonia resolved. Adjusted diabetes medications for better control.
Date: December 5, 2023

Reason for Visit: Neurology Follow-up
Notes: Fine-tuned Parkinson's medication regimen. Recommended ongoing physical therapy.
"""  # noqa: E501

anoncat_help_content = """Demo app for the deidentification of private health information using the CogStack AnonCAT model

Please DO NOT test with any real sensitive PHI data.

Local validation and fine-tuning available via [MedCATtrainer](
https://github.com/CogStack/cogstack-nlp/tree/main/medcat-trainer).
Email us, [contact@cogstack.org](mailto:contact@cogstack.org), to discuss model access,
model performance, and your use case.

The following PHI items have been trained:

| PHI Item | Description |
|----------|-------------|
| NHS Number | UK National Health Service Numbers. |
| Name | All names, first, middle, last of patients, relatives, care providers etc. Importantly, does not redact conditions that are named after a name, e.g. "Parkinsons's disease". |
| Date of Birth | DOBs. Does not include other dates that may be in the record, i.e. dates of visit etc. |
| Hospital Number | A unique number provided by the hospital. Distinct from the NHS number |
| Address Line | Address lines - first, second, third or fourth |
| Postcode | UK postal codes - 6 or 7 alphanumeric codes as part of addresses |
| Telephone Number | Telephone numbers, extensions, mobile / cell phone numbers |
| Email | Email addresses |
| Initials | Patient, relatives, care provider name initials. |
"""  # noqa: E501
