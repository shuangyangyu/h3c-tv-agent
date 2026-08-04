from h3c_tv_agent.log_feedback import clear_log_feedback, make_mqtt_feedback_publisher, register_log_feedback


def test_log_feedback_acl_event():
    published = []
    statuses = []

    def publish_state(tv, state, attrs=None):
        published.append((tv, state, attrs))

    def publish_status(s):
        statuses.append(s)

    clear_log_feedback()
    register_log_feedback(make_mqtt_feedback_publisher(publish_state, publish_status))

    from h3c_tv_agent.log_feedback import log_feedback_processor

    log_feedback_processor(
        None,
        "info",
        {
            "event": "acl updated",
            "tv": "master_bedroom",
            "action": "deny",
            "result": "ok",
            "state": "OFF",
            "deny_rule": 15,
            "duration_ms": 100,
        },
    )
    assert published == [
        (
            "master_bedroom",
            "OFF",
            {
                "name": "主卧电视",
                "ip": "192.168.1.24",
                "deny_rule": 15,
                "feedback_source": "log:acl",
                "action": "deny",
                "duration_ms": 100,
            },
        )
    ]
    clear_log_feedback()


def test_log_feedback_ignores_fail():
    published = []
    clear_log_feedback()
    register_log_feedback(
        make_mqtt_feedback_publisher(lambda *a, **k: published.append(1), lambda s: None)
    )
    from h3c_tv_agent.log_feedback import log_feedback_processor

    log_feedback_processor(
        None,
        "error",
        {"tv": "master_bedroom", "action": "deny", "result": "fail", "state": "OFF"},
    )
    assert published == []
    clear_log_feedback()
