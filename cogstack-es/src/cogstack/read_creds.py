import os


CS_HOSTS_ENV = "COGSTACK_HOSTS"
CS_UN_ENV = "COGSTACK_USERNAME"
CS_PW_ENV = "COGSTACK_PASSWORD"
CS_API_KEY_ENV = "COGSTACK_API_KEY"


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
    api_key = (
        # TODO: is this correct?
        {"encoded": api_key}
        if (api_key := os.environ.get(CS_API_KEY_ENV))
        else None
    )
    username = os.getenv(CS_UN_ENV)
    password = os.getenv(CS_PW_ENV)
    return hosts, api_key, (username, password)
