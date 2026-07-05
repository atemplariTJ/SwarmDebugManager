from backend.fleet import build_fleet, make_robot_ip, robot_payload


def test_make_robot_ip_uses_existing_frontend_rule():
    assert make_robot_ip("10.42.0", 1, 0) == "10.42.0.1"
    assert make_robot_ip("10.42.0.", 30, 2) == "10.42.0.32"


def test_build_fleet_returns_existing_frontend_shape():
    robots = build_fleet("10.42.0", offset=0, count=2, port=22)
    payload = robot_payload(robots[0])

    assert payload["id"] == "R01"
    assert payload["idNum"] == 1
    assert payload["ip"] == "10.42.0.1"
    assert payload["status"] == "offline"
    assert payload["state"] == "idle"
    assert payload["errCount"] == 0


def test_build_fleet_merges_cached_status():
    robots = build_fleet(
        "10.42.0",
        offset=1,
        count=1,
        port=22,
        statuses={"R01": {"status": "online", "state": "idle", "ping": 12, "batt": 55}},
    )
    payload = robot_payload(robots[0])

    assert payload["ip"] == "10.42.0.2"
    assert payload["status"] == "online"
    assert payload["ping"] == 12
    assert payload["batt"] == 55
