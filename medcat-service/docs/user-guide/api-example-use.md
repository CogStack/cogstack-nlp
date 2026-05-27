## API Example use

This page gives examples for how to call the service and what will be returned.


Assuming that the application is running on the `localhost` with the API exposed on port `5000`, one can run:

```bash
curl -XPOST http://localhost:5000/api/process \
  -H 'Content-Type: application/json' \
  -d '{"content":{"text":"The patient was diagnosed with leukemia."}}'
```

and the received result:

```json
{
 "result": {"text": "The patient was diagnosed with leukemia.",
 
 "annotations": {"entities": {"0": {"pretty_name": "Patients", "cui": "C0030705", "type_ids": ["T101"], "types": ["Patient or Disabled Group"], "source_value": "patient", "detected_name": "patient", "acc": 0.99, "context_similarity": 0.99, "start": 4, "end": 11, "icd10": [], "ontologies": [], "snomed": [], "id": 0, "meta_anns": {"Status": {"value": "Affirmed", "confidence": 0.9999303817749023, "name": "Status"}}}, "1": {"pretty_name": "Diagnosis", "cui": "C0011900", "type_ids": ["T060"], "types": ["Diagnostic Procedure"], "source_value": "diagnosed", "detected_name": "diagnosed", "acc": 0.6657139492748229, "context_similarity": 0.6657139492748229, "start": 16, "end": 25, "icd10": [], "ontologies": [], "snomed": [], "id": 1, "meta_anns": {"Status": {"value": "Affirmed", "confidence": 0.9999918341636658, "name": "Status"}}}, "2": {"pretty_name": "leukemia", "cui": "C0023418", "type_ids": ["T191"], "types": ["Neoplastic Process"], "source_value": "leukemia", "detected_name": "leukemia", "acc": 0.2572544372951888, "context_similarity": 0.2572544372951888, "start": 31, "end": 39, "icd10": [], "ontologies": [], "snomed": [], "id": 2, "meta_anns": {"Status": {"value": "Affirmed", "confidence": 0.9999804496765137, "name": "Status"}}}}, "tokens": []},
 
 "success": true,
 "timestamp": "2021-11-11T11:54:28.856+00:00"
 },
 "medcat_info": {"service_app_name": "MedCAT", "service_language": "en", "service_version": "1.2.5", "service_model": "MedMen"}
}
```

Additional DE-ID query sample (make sure you have a de-id model loaded):

```bash
curl -XPOST <http://localhost:5555/api/process> \
  -H 'Content-Type: application/json' \
  -d '{"content":{"text":"Patient Information: Full Name: John Michael Doe \n Gender: Male \n Date of Birth: January 15, 1975 (Age: 49) \n Patient ID: 567890123 \n Address: 1234 Elm Street, Springfield, IL 62701 \n Phone Number: (555) 123-4567 \n Email: <johnmdoe@example.com> \n Emergency Contact: Jane Doe (Wife) \n Phone: (555) 987-6543 \n Relationship: Spouse"}}'
```

Make sure you have the following option enabled in `envs/(medcat|medcat_deid).env` , `DEID_MODE=True`.

process_bulk example :

```bash
curl -XPOST http://localhost:5000/api/process_bulk \
 -H 'Content-Type: application/json' \
 -d '{"content": [{"text":"The patient was diagnosed with leukemia."}, {"text": "The patient was diagnosed with cancer."}] }'
```

example bulk result :

```json
{
  "result": [
    {
      "text": "The patient was diagnosed with leukemia.",
      "annotations": {
        "0": {
          "pretty_name": "Patients",
          "cui": "C0030705",
          "type_ids": [
            "T101"
          ],
          "types": [
            "Patient or Disabled Group"
          ],
          "source_value": "patient",
          "detected_name": "patient",
          "acc": 0.99,
          "context_similarity": 0.99,
          "start": 4,
          "end": 11,
          "id": 0,
          "meta_anns": {
            "Status": {
              "value": "Affirmed",
              "confidence": 0.9999303817749023,
              "name": "Status"
            }
          }
        },
        "1": {
          "pretty_name": "Diagnosis",
          "cui": "C0011900",
          "type_ids": [
            "T060"
          ],
          "types": [
            "Diagnostic Procedure"
          ],
          "source_value": "diagnosed",
          "detected_name": "diagnosed",
          "acc": 0.6657139492748229,
          "context_similarity": 0.6657139492748229,
          "start": 16,
          "end": 25,
          "id": 1,
          "meta_anns": {
            "Status": {
              "value": "Affirmed",
              "confidence": 0.9999918341636658,
              "name": "Status"
            }
          }
        },
        "2": {
          "pretty_name": "leukemia",
          "cui": "C0023418",
          "type_ids": [
            "T191"
          ],
          "types": [
            "Neoplastic Process"
          ],
          "source_value": "leukemia",
          "detected_name": "leukemia",
          "acc": 0.2572544372951888,
          "context_similarity": 0.2572544372951888,
          "start": 31,
          "end": 39,
          "id": 2,
          "meta_anns": {
            "Status": {
              "value": "Affirmed",
              "confidence": 0.9999804496765137,
              "name": "Status"
            }
          }
        }
      },
      "success": true,
      "timestamp": "2021-12-08T18:49:55.255+00:00"
    },
    {
      "text": "The patient was diagnosed with cancer.",
      "annotations": {
        "0": {
          "pretty_name": "Patients",
          "cui": "C0030705",
          "type_ids": [
            "T101"
          ],
          "types": [
            "Patient or Disabled Group"
          ],
          "source_value": "patient",
          "detected_name": "patient",
          "acc": 0.99,
          "context_similarity": 0.99,
          "start": 4,
          "end": 11,
          "id": 0,
          "meta_anns": {
            "Status": {
              "value": "Affirmed",
              "confidence": 0.9999236464500427,
              "name": "Status"
            }
          }
        },
        "2": {
          "pretty_name": "cancer diagnosis",
          "cui": "C0920688",
          "type_ids": [
            "T060"
          ],
          "types": [
            "Diagnostic Procedure"
          ],
          "source_value": "diagnosed with cancer",
          "detected_name": "diagnosed~with~cancer",
          "acc": 1,
          "context_similarity": 1,
          "start": 16,
          "end": 37,
          "id": 2,
          "meta_anns": {
            "Status": {
              "value": "Affirmed",
              "confidence": 0.9999957084655762,
              "name": "Status"
            }
          }
        }
      },
      "success": true,
      "timestamp": "2021-12-08T18:49:55.255+00:00"
    }
  ],
  "medcat_info": {
    "service_app_name": "MedCAT",
    "service_language": "en",
    "service_version": "1.2.6",
    "service_model": "MedMen"
  }
}

```

<strong>IMPORTANT info regarding annotation output style</strong>
As the changes from MedCAT intoduced dictionary annotation/entity output.

The mode in which annotation entities should be outputted in the JSON response,
   by default this was outputted as a "list" of dicts in older versions, so the output would be :

   ```json
    {"annotations": [{"id": "0", "cui" : "C1X..", ..}, {"id":"1", "cui": "...."}]}
   ```

   newer versions of MedCAT (1.2+) output entities as a dict, where the id of the entity is a key and the rest of the data is a value, so for "dict",
   the output is

   ```json
    {"annotations": [{"0": {"cui": "C0027361", "id": 0,.....}, "1": {"cui": "C001111", "id": 1......}}]}
   ```

This setting can be configured in the ```./env/medcat.env``` file, using the ```MEDCAT_ANNOTATIONS_ENTITY_OUTPUT_MODE``` variable.
By default, the output of these entities is set to respect the output of the MedCAT package, hence the latter will be used. Please change the above mentioned env variable and make sure your CogStack-Nifi annotation script is adapted accordingly.

Please note that the returned NLP annotations will depend on the underlying model used. For evaluation, we can only provide a very basic model trained on [MedMentions](https://github.com/chanzuckerberg/MedMentions). Models utilising [SNOMED CT](https://www.england.nhs.uk/digitaltechnology/digital-primary-care/snomed-ct/) or [UMLS](https://www.nlm.nih.gov/research/umls/index.html) may require applying for licenses from the copyright holders.