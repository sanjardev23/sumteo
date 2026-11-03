from sumteo.events.escalation import AckTracker


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_unacknowledged_critical_escalates_once_after_the_timeout():
    clock = FakeClock()
    tracker = AckTracker(timeout_s=60, clock=clock)
    tracker.track("e1", "CRITICAL")
    clock.now = 59.0
    assert tracker.due() == []
    clock.now = 60.0
    assert tracker.due() == ["e1"]
    clock.now = 200.0
    assert tracker.due() == []                    # re-sent once, not every second


def test_acknowledged_critical_does_not_escalate():
    clock = FakeClock()
    tracker = AckTracker(timeout_s=60, clock=clock)
    tracker.track("e1", "CRITICAL")
    clock.now = 30.0
    tracker.ack("e1")
    clock.now = 120.0
    assert tracker.due() == []


def test_only_critical_is_tracked():
    clock = FakeClock()
    tracker = AckTracker(timeout_s=60, clock=clock)
    tracker.track("w", "WARNING")
    tracker.track("i", "INFO")
    tracker.track("a", "CRITICAL", acknowledged=True)
    clock.now = 120.0
    assert tracker.due() == []
