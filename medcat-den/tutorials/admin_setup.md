# MedCAT Model Den – Admin Guide

This guide is for **system administrators** who are setting up the MedCAT model den for their users  
(e.g. on a shared JupyterHub instance, cluster, or server).

End-users generally **should not need to configure anything** – the admin should set up the environment variables once, and users will inherit them.

---

## 1. Environment Variables

| Environmetnal variable name    | Values | Description | Comments |
| ------------------------------ | ------ | ----------- | -------- |
| MEDCAT_DEN_TYPE                | `LOCAL_USER`, `LOCAL_MACHINE` | The type of den to use | Currently, only local dens have been implemented, but remote (e.g MedCATtery or even cloud) options can be implemented. |
| MEDCAT_DEN_PATH                | str    | The save path (for local backends) | This is normally automatically specified based on OS and whether it's user or machien local. But can be overwritten here as well. |
| MEDCAT_DEN_REMOTE_HOST         | str    | The host path to the remote (e.g MedCATtery) | This is currently not yet implemented |
| MEDCAT_DEN_LOCAL_CACHE_PATH            | str | The local cache path (if required). | This allows caching of models from remote dens |
| MEDCAT_DEN_LOCAL_CACHE_EXPIRATION_TIME | int | The expriation time for local cache (in seconds) | The default is 10 days |
| MEDCAT_DEN_LOCAL_CACHE_MAX_SIZE        | int | The maximum size of the cache in bytes | The default is 100 GB |
| MEDCAT_DEN_LOCAL_CACHE_EVICTION_POLICY | str | The eviction polciy for the local cache | The default is LRU |

---

## 2. Mandatory Configuration

> ⚠️ At a minimum, **you must set** the den type.

- For most setups:  
  ```bash
  export MEDCAT_DEN_TYPE=LOCAL_MACHINE
- If you're using a MEDCATTERY den (not yet implemented at 2025-08-29)
  - `export MEDCAT_DEN_TYPE=MEDCATTERY`
  - `export MEDCAT_DEN_REMOTE_HOST=https://den.example.org`
    - This should be a link to the MedCATtery service

---

## 3. Optional Configuration

Optional settings depend on your chosen den type:
- REMOTE dens: strongly recommended to configure a local cache
  ```
  export MEDCAT_DEN_LOCAL_CACHE_PATH=/srv/medcat/cache
  export MEDCAT_DEN_LOCAL_CACHE_MAX_SIZE=$((100*1024*1024*1024))  # 100GB
  export MEDCAT_DEN_LOCAL_CACHE_EXPIRATION_TIME=$((10*24*60*60))  # 10 days
  ```

---

## 4. Where to Configure Environment Variables

You only need to configure these once, depending on your deployment:

- Linux (system-wide)
    ```bash
    # /etc/profile.d/medcat.sh
    export MEDCAT_DEN_TYPE="LOCAL_MACHINE"
    export MEDCAT_DEN_PATH="/srv/medcat/models"
    ```
- JupyterHub (per-spawner)
    ```python
    # jupyterhub_config.py
    c.Spawner.environment = {
        "MEDCAT_DEN_TYPE": "LOCAL_MACHINE",
        "MEDCAT_DEN_LOCAL_CACHE_PATH": "/srv/medcat/cache",
    }
    ```
- Docker / Kubernetes
    ```yaml
    # docker-compose.yml
    environment:
    - MEDCAT_DEN_TYPE=LOCAL_MACHINE
    - MEDCAT_DEN_PATH=/srv/medcat/models
    - MEDCAT_DEN_LOCAL_CACHE_PATH=/srv/medcat/cache
    ```

---

## 5. Best Practices

- If you're working alone
  - There is generally no need for MedCAT-den unless you have a very large number of models
  - If you do need MedCAT-den, the `LOCAL_USER` type should be sufficient
  - You certainly shouldn't use a local cache in addition
- If the target is a server
  - If there is a MedCATtery service available
    - Use `MEDCATTERY` for den type
    - Use a local cache
      - E.g `MEDCAT_DEN_LOCAL_CACHE_PATH=/var/tmp/medcat-den`
      - NOTE: Make sure the path is accessible to all user (in terms of read/write)
  - If there is no MedCATtery service available
    - Use `LOCAL_MACHINE` for den tyep
    - Do NOT use a local cache (files are local already)


## 6. FAQ

**Q: Do end-users need to set these environment variables themselves?**

**A:** No. The admin should configure them globally (system-wide, JupyterHub spawner, or container config). Users’ notebooks will then inherit them automatically.


**Q: What happens if I don’t set MEDCAT_DEN_TYPE?**

**A:** The den will default to the `USER_LOCAL` option. It will still be somewhat useful. But only at a per user basis.

**Q: Should I use `LOCAL_USER` or `LOCAL_MACHINE`?**
**A:**
- Use `LOCAL_MACHINE` if you want all users to share the same den and model storage.
- Use `LOCAL_USER` if each user should have their own private den in their home directory.


**Q: Is `MEDCATTERY` supported yet?**

**A:** Not at this time. The `MEDCATTERY` type and `MEDCAT_DEN_REMOTE_HOST` variable are placeholders for future support.


**Q: How much space should I allocate for caches?**

**A:** Models can be large (up to 3GB each, sometimes even more). The default is 100GB. Adjust based on the number of models you expect and whether multiple users share the same cache.


**Q: Can users override the admin defaults?**

**A:** Yes, if they set the variables in their own ~/.bashrc or JupyterHub “environment” configuration. Or even explitly pass them when initialising a den. Admin-set values should be considered defaults, not locks.


**Q: What eviction policies are supported for cache?**

**A:** The backend (`diskcache`) supports LRU (`least-recently-used`), LRS (`least-recently-stored`), LFU (`least-frequently-used`), and `none` (disables evictions).


**Q: A local den and a local cache? What's the difference?**

**A:** A local den is a (semi) permanent location to save your models at.
It serves as a replacement to the remote model storage / lifecycle target (such as MedCATtery).
A local cache is designed to cache files downloaded from the remote store. It is designed to clear the data if/when it is no longer needed.
While the two can be used together, it doesn't generally make a lot of sense (unless the local den is tied to a slow network attached storage device).

