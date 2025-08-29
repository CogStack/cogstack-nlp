from typing import List
# CogStack login details
# Any questions on what these details are please contact
# your local CogStack administrator.

hosts: List[str] = [
    # "https://cogstack-es-1:9200",
    #  # This is an example of a CogStack ElasticSearch instance.
 ]  # This is a list of your CogStack ElasticSearch instances.

# These are your login details (either via http_auth or API) Should be in
# string format
username = None
password = None
# If you are using API key authentication
# Use either "id" and "api_key" or "encoded" field, or both.
api_key = {
    # This is the API key id issued by your cogstack administrator.
    "id": "",
    # This is the api key issued by your cogstack administrator.
    "api_key": "",
    # This is the encoded api key issued by your cogstack administrator.
    "encoded": "",
}
