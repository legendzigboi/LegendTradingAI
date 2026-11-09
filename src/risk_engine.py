from src.state import SYSTEM_PAUSED
import src.state as state

def check_circuit_breaker():
    if state.SYSTEM_PAUSED:
        return False, "⛔ System manually PAUSED."
    return True, "✅ Risk Check Passed."

def set_pause(status: bool):
    state.SYSTEM_PAUSED = status
    return state.SYSTEM_PAUSED
