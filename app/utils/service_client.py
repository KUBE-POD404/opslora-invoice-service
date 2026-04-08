import requests
import uuid
from app.core.logging_config import request_id_ctx

def authenticated_get(url, token):

    request_id = request_id_ctx.get() or str(uuid.uuid4())

    return requests.get(
        url,
        headers={
            "Authorization": token,
            "X-Request-ID": request_id
        },
        timeout=5
    )