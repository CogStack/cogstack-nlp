import os


CS_HOSTS_ENV = "COGSTACK_HOSTS"
CS_UN_ENV = "COGSTACK_USERNAME"
CS_PW_ENV = "COGSTACK_PASSWORD"
CS_API_KEY_ID_ENV = "COGSTACK_API_KEY_ID"
CS_API_KEY_KEY_ENV = "COGSTACK_API_KEY"
CS_API_KEY_ENCODED_ENV = "COGSTACK_API_KEY_ENCODED"


def _read_api_key() -> dict | None:
    key_id = os.getenv(CS_API_KEY_ID_ENV)
    api_key = os.getenv(CS_API_KEY_KEY_ENV)
    api_key_encoded = os.getenv(CS_API_KEY_ENCODED_ENV)
    out_dict = {}
    if key_id:
        out_dict["id"] = key_id
    if api_key:
        out_dict["api_key"] = api_key
    if api_key_encoded:
        out_dict["encoded"] = api_key_encoded
    return out_dict or None


def read_from_env() -> tuple[list[str],
                             dict | None,
                             tuple[str | None, str | None]]:
    """Read hosts and credentials from environmental vairables.

    Returns:
        tuple[list[str],
              dict | None,
              tuple[str | None, str | None]]:
                The hosts, the API credentials, and
                the username-password pair.
    """
    hosts = os.getenv(CS_HOSTS_ENV, "").split(",")
    api_key = _read_api_key()
    username = os.getenv(CS_UN_ENV)
    password = os.getenv(CS_PW_ENV)
    return hosts, api_key, (username, password)
