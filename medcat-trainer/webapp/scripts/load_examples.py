import os

import pandas as pd
import requests
from time import sleep
import json


def main(port=8000,
         model_pack_tmp_file='/home/model_pack.zip',
         dataset_tmp_file='/home/ds.csv',
         initial_wait=15):

    val = os.environ.get('LOAD_EXAMPLES')
    if val is not None and val not in ('1', 'true', 't', 'y'):
        print('Found Env Var LOAD_EXAMPLES is False, not loading example data, cdb, vocab and project')
        return

    print('Found Env Var LOAD_EXAMPLES, waiting 15 seconds for API to be ready...')
    URL = f'http://localhost:{port}/api/'
    sleep(initial_wait)

    print('Checking for default projects / datasets / CDBs / Vocabs')
    while True:
        try:
            # check API is available
            if requests.get(URL).status_code == 200:
                # check API default username and pass are available.
                payload = {"username": "admin", "password": "admin"}
                resp = requests.post(f"{URL}api-token-auth/", json=payload)
                if resp.status_code != 200:
                    break

                headers = {
                    'Authorization': f'Token {json.loads(resp.text)["token"]}',
                }

                # check concepts DB, vocab, datasets and projects are empty
                resp_model_packs = requests.get(f'{URL}modelpacks/', headers=headers)
                resp_ds = requests.get(f'{URL}datasets/', headers=headers)
                resp_projs = requests.get(f'{URL}project-annotate-entities/', headers=headers)
                all_resps = [resp_model_packs, resp_ds, resp_projs]

                codes = [r.status_code == 200 for r in all_resps]

                if all(codes) and all(len(r.text) > 0 and json.loads(r.text)['count'] == 0 for r in all_resps):
                    print("Found No Objects. Populating Example: Model Pack, Dataset and Project...")
                    # download example model pack and dataset
                    print("Downloading example model pack...")
                    model_pack_file = requests.get('https://trainer-example-data.s3.eu-north-1.amazonaws.com/medcat2_model_pack_0f66077250cc2957.zip')
                    with open(model_pack_tmp_file, 'wb') as f:
                        f.write(model_pack_file.content)

                    print("Downloading example dataset")
                    ds = requests.get('https://trainer-example-data.s3.eu-north-1.amazonaws.com/dr_notes.csv')
                    with open(dataset_tmp_file, 'w') as f:
                        f.write(ds.text)

                    ds_dict = pd.read_csv(dataset_tmp_file).loc[:, ['name', 'text']].to_dict()
                    create_example_project(URL, headers, model_pack_tmp_file, 'M-IV_NeuroNotes', ds_dict,
                                           'Example Project - Model Pack (Diseases / Symptoms / Findings)')


                    # clean up temp files
                    os.remove(model_pack_tmp_file)
                    os.remove(dataset_tmp_file)
                    break
                else:
                    print('Found at least one object amongst model packs, datasets & projects. Skipping example creation')
                    break
        except ConnectionRefusedError:
            print(f'Connection refused to {URL}. Retrying in 5 seconds...')
            sleep(5)
            continue
        except requests.exceptions.ConnectionError:
            print(f'Connection error to {URL}. Retrying in 5 seconds...')
            sleep(5)
            continue


def create_example_project(url, headers, model_pack, ds_name, ds_dict, project_name):
    print('Creating Model Pack / Dataset / Project in the Trainer')
    res_model_pack_mk = requests.post(f'{url}modelpacks/', headers=headers,
                                      data={'name': 'Example Model Pack'},
                                      files={'model_pack': open(model_pack, 'rb')})
    model_pack_id = json.loads(res_model_pack_mk.text)['id']

    # Upload the dataset
    payload = {
        'dataset_name': ds_name,
        'dataset': ds_dict,
        'description': f'Clinical texts from MIMIC-IV'
    }
    resp = requests.post(f'{url}create-dataset/', json=payload, headers=headers)
    ds_id = json.loads(resp.text)['dataset_id']

    user_id = json.loads(requests.get(f'{url}users/', headers=headers).text)['results'][0]['id']

    # Create the project
    payload = {
        'name': project_name,
        'description': 'Example projects using example psychiatric clinical notes from '
                       'https://www.mtsamples.com/',
        'cuis': '',
        'annotation_guideline_link': 'https://docs.google.com/document/d/1xxelBOYbyVzJ7vLlztP2q1Kw9F5Vr1pRwblgrXPS7QM/edit?usp=sharing',
        'dataset': ds_id,
        'model_pack': model_pack_id,
        'members': [user_id]
    }
    requests.post(f'{url}project-annotate-entities/', json=payload, headers=headers)
    print('Successfully created the example project')


if __name__ == '__main__':
    main(port=8001, initial_wait=3,
            model_pack_tmp_file='/Users/foooo/Downloads/model_pack.zip',
            dataset_tmp_file='/Users/fooo/Downloads/ds.csv')
