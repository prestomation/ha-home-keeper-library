"""Docker integration: a service call fires the documented bus event.

The HA config has an automation that writes the last
``home_keeper_library_room_added`` event to an ``input_text`` helper, so the
test reads, over real Home Assistant, that the event fired with the right
payload. An integrator sees the event the same way.
"""

from __future__ import annotations

import time


def test_add_room_fires_the_room_added_event(api):
    resp = api.post(
        "/api/services/home_keeper_library/add_room?return_response",
        json={"name": "Integration den"},
    )
    assert resp.status_code == 200, resp.text
    room_id = resp.json()["service_response"]["room"]["id"]
    deadline = time.monotonic() + 10
    state = {}
    while time.monotonic() < deadline:
        state = api.get("/api/states/input_text.hkl_last_event").json()
        if state.get("state", "").startswith("room_added:"):
            break
        time.sleep(0.5)
    assert state["state"] == f"room_added:{room_id}:Integration den"
    api.post(
        "/api/services/home_keeper_library/delete_room",
        json={"room_id": room_id},
    )
