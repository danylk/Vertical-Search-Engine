import os
from dotenv import load_dotenv
from elasticsearch7 import Elasticsearch

load_dotenv()

# Connection settings come from the environment (see .env.example) so that
# no credentials are committed to the repository.
INDEX_NAME = os.environ.get('ES_INDEX', 'finalindex')
AUTHOR_NAME = os.environ.get('ES_AUTHOR', 'Sunkwan')


def get_client():
    cloud_id = os.environ.get('ES_CLOUD_ID')
    user = os.environ.get('ES_USERNAME', 'elastic')
    password = os.environ.get('ES_PASSWORD')

    if cloud_id:
        return Elasticsearch(cloud_id=cloud_id, http_auth=(user, password))
    # Fall back to a local cluster, e.g. one started with Docker
    return Elasticsearch(os.environ.get('ES_HOST', 'http://localhost:9200'))
