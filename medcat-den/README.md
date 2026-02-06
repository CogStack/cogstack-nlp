# MedCAT-den

This is a remote (or user / machine local) storage addon for MedCAT.
The idea is that instead of having duplicate models on disk for every project and user, you can reuse the ones centrally saved somewhere else.

However, the nuance here is that the model still gets loaded into memory locally.
This is so that we do not have to worry about data moving the underlying text data between machines.

## The idea / functionality

The current idea is that the den will provide the following functionality
 - Allow listing of available models
 - Allow fetching a model
 - Allow pushing a model (after fine tuning)

The workflow for the user would be (roughly) as follows:
 - Instantiate a den instance
   - The default could be set up solely by environmental values
   - Though if nothing is set, it may default to a lower-functionality user-specific storage
 - Use the den to get a list of available models
   - Each model has a hash and some description
 - Fetch a model from the den to use in local memory
   - This downloads the model pack to a temporary folder
   - Then extracts it there
   - Subsequently loads it into memory
   - And removes the temporary files
 - Use model as needed
   - Either inference
   - Or fine-tuning
 - If fine-tuning done, can push it back to the den
   - This will pack up the model to a temporary folder
   - Then push the .zip as an experiment to the remote

## How to use

To use a the MedCAT-den, juse get yourself a den:
```python
from medcat_den.den import get_default_den
den = get_default_den()
```
And then list your available models:
```python
models = den.list_available_models()
print("Models:", models)
```
Then get the specific model pack
```python
cat = den.fetch_model(models[0])
```
Once you're done with your model, you can push it back using
```python
den.push_model(cat, "Did some fine-tuning")
```

### Injecting the den to `CAT.load_model_pack`

There is now the option to inject the den functionality directly into `CAT.load_model_pack`.
That is to say, if this is used, `CAT.load_model_pack` will use MedCAT-Den to fetch the model from either the remote or local den.

There are a number of ways to do this.
1. You can use the context manager approach:
    ```python
    from medcat_den.injection import injected_den
    with injected_den():
      pass # Do the model load
    # now the injection is turned off
    ```
2. You can directly call the injector before using anything else:
    ```python
    from medcat_den.injection import inject_into_medcat, uninject_into_medcat
    inject_into_medcat()
    # do the model load(s)
    uninject_into_medcat()  # undo injection
    ```

As a note, the `inject_into_medcat` and `injected_den` methods allow you pass a few options:
 - `den_getter`: The method to get the relevant den for your use case. Defaults to `get_default_den`.
 - `model_name_mapper`: The model name mapper (if specified). Can either be a `dict` based mapping or a function based one.
 - `prefix`: The prefix for the Den-based models. If not specified, all models are expected to be den-based ones. Otherwise, only prefixed models will be loaded from the den and others will be loaded off disk.

### Using the den as a runtime injection target

Given the above, one might find themselves in a situation where they want to run the injector as part of an entire runtime.
There's ways of doing that as well:
1. Running a module
    ```bash
    # instead of
    python -m path.to.my_module arg1 arg2
    # you can do
    python -m medcat_den --with-injection -m path.to.my_module arg1 arg2
    ```
2. Running a script
    ```bash
    # instead of
    python -m path/to/my_module.py arg1 arg2
    # you can do
    python -m medcat_den --with-injection python -m path/to/my_module.py arg1 arg2
    ```
3. Running a code string
    ```bash
    # instead of
    python -c "from my_module import do_my_stuff;do_my_stuff()"
    # you can do
    python -m medcat_den --with-injection python -c "from my_module import do_my_stuff;do_my_stuff()"
    ```
4. Running interactively
    ```bash
    # instead of
    python
    # you can do
    python -m medcat_den --with-injection python -i
    ```
4. Running interactively after something else (i.e a module or a script)
    ```bash
    # instead of
    python <whatever>
    # you can do
    python -m medcat_den --with-injection python -i <whatever>
    ```

## Multi-Backend Den

It is possible to configure `MedCAT-den` to use multiple backends simultaneously, allowing you to access different model repositories (e.g., a local user cache and a remote MedCATtery instance) through a single `Den` object. This is achieved by providing a JSON configuration file via an environment variable.

### Configuration

Create a JSON file (e.g., `multi_backend_config.json`) that defines your backends. Each backend is given a unique name and its own configuration parameters, similar to how a single `Den` is configured. You can also specify a `default_backend`.

Here's an example:

```json
{
    "default_backend": "user_local_dev",
    "backends": {
        "user_local_dev": {
            "type": "local_user",
            "location": "/path/to/my/user_local_den_dev"
        },
        "medcattery_prod": {
            "type": "medcattery",
            "host": "https://medcattery.example.com",
            "credentials": {
                "api_key": "YOUR_API_KEY"
            }
        }
    }
}
```

To enable this multi-backend configuration, set the `MEDCAT_DEN_BACKENDS_JSON` environment variable to the path of your JSON configuration file:

```bash
export MEDCAT_DEN_BACKENDS_JSON="/path/to/your/multi_backend_config.json"
```

### Usage

When a multi-backend den is configured, you can specify which backend to use for a particular operation by providing the `backend_name` argument to the `Den` methods:

```python
from medcat_den.den import get_default_den

den = get_default_den()

# List models from the default backend (user_local_dev in the example above)
default_models = den.list_available_models()

# List models from a specific backend (medcattery_prod)
medcattery_models = den.list_available_models(backend_name="medcattery_prod")

# Fetch a model from a specific backend
cat_model = den.fetch_model(medcattery_models[0], backend_name="medcattery_prod")
```

## Settings

The above created a default den.
If no prior configuration is done, this will be a user-local model cache.

However, there's a set of environmental variables that can be set in order to curate the default den:
| Environmental variable name    | Values | Description | Comments |
| ------------------------------ | ------ | ----------- | -------- |
| MEDCAT_DEN_TYPE                | `LOCAL_USER`, `LOCAL_MACHINE`, `MEDCATTERY` | The type of den to use | Currently, only local dens have been implemented, but remote (e.g MedCATtery or even cloud) options can be implemented. |
| MEDCAT_DEN_PATH                | str    | The save path (for local backends) | This is normally automatically specified based on OS and whether it's user or machine local. But can be overwritten here as well. |
| MEDCAT_DEN_REMOTE_HOST         | str    | The host path to the remote (e.g MedCATtery) | This is currently not yet implemented |
| MEDCAT_DEN_LOCAL_CACHE_PATH            | str | The local cache path (if required). | This allows caching of models from remote dens |
| MEDCAT_DEN_LOCAL_CACHE_EXPIRATION_TIME | int | The expiration time for local cache (in seconds) | The default is 10 days |
| MEDCAT_DEN_LOCAL_CACHE_MAX_SIZE        | int | The maximum size of the cache in bytes | The default is 100 GB |
| MEDCAT_DEN_LOCAL_CACHE_EVICTION_POLICY | str | The eviction policy for the local cache | The default is LRU |
| MEDCAT_DEN_REMOTE_ALLOW_PUSH_FINETUNED | bool | Whether to allow locally fine tuned model to be pushed to remote dens | Defaults to False |
| MEDCAT_DEN_REMOTE_ALLOW_LOCAL_FINE_TUNE | bool | Whether to allow local fine tuning for remote dens | Defaults to False |
| MEDCAT_DEN_BACKENDS_JSON       | str | Path to a JSON file configuring multiple backends | If set, this overrides all other `MEDCAT_DEN_*` settings for the default den configuration, and enables multi-backend mode. |

When creating a den, the resolver will use the explicitly passed values first, and if none are provided, it will default to the ones defined in the environmental variables.
