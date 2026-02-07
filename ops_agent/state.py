import time
from enum import Enum

class AgentState(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    RECOVERY_IN_PROGRESS = "RECOVERY_IN_PROGRESS"
    RECOVERY_SUCCEEDED = "RECOVERY_SUCCEEDED"
    RECOVERY_FAILED = "RECOVERY_FAILED"

class StateTracker:
    def __init__(self, failure_threshold: int, cooldown_seconds: int, max_attempts_per_incident: int = 1):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.max_attempts_per_incident = max(1, int(max_attempts_per_incident))

        self.fail_count = 0
        self.attempts_this_incident = 0
        self.state = AgentState.OK
        self.last_action_ts = 0

    def reset_incident(self):
        """Called when the incident is cleared (e.g., NAS reachable again)."""
        self.fail_count = 0
        self.attempts_this_incident = 0
        self.state = AgentState.OK
        # Do not reset last_action_ts; cooldown is about actions, not success.

    def record_success(self):
        self.reset_incident()

    def record_failure(self):
        # If we've already declared failure for this incident, stay there until reset_incident().
        if self.state == AgentState.RECOVERY_FAILED:
            return

        self.fail_count += 1
        if self.fail_count >= self.failure_threshold:
            self.state = AgentState.DEGRADED

    def can_act(self) -> bool:
        return (time.time() - self.last_action_ts) > self.cooldown_seconds

    def can_attempt_recovery(self) -> bool:
        return self.attempts_this_incident < self.max_attempts_per_incident

    def record_recovery_attempt(self):
        self.attempts_this_incident += 1

    def mark_action(self):
        self.last_action_ts = time.time()
        self.state = AgentState.RECOVERY_IN_PROGRESS

    def mark_failed(self):
        self.state = AgentState.RECOVERY_FAILED
