import json
import time

import requests

def test_creation():
    time.sleep(1)
    new_login_payload = {
        "user_id": "x" * 24,
        "key": "new_login",
        "target_email": "reciever@mail.ru",
    }
    valid_response = requests.post(
        "http://127.0.0.1:8000/create", json=new_login_payload
    )
    assert valid_response.status_code == 201

    list_endpoint_response = requests.get(
        "http://127.0.0.1:8000/list",
        params={"user_id": "x" * 24, "skip": 0, "limit": 3},
    )
    assert list_endpoint_response.status_code == 200
    # assert len(json.loads(list_endpoint_response.text)['data']) == 1
    assert len(json.loads(list_endpoint_response.text)["data"]) == 1

    notification_id = json.loads(list_endpoint_response.text)["data"][0]["id"]

    read_endpoint_response = requests.post(
        "http://localhost:8000/read",
        params={"user_id": "x" * 24, "notification_id": notification_id},
    )
    assert read_endpoint_response.status_code == 200
