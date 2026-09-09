"""Test FSM (SPEC §5): transizioni valide, debounce, rientro."""


def _fsm():
    from src.state_machine import StateMachine

    return StateMachine(debounce_ms=0)


def test_initial_state_is_seguilinea():
    from src.state_machine import State

    assert _fsm().state == State.SEGUILINEA


def test_green_right_requests_verde_dx():
    import time

    from src.state_machine import Perception, State, StateMachine

    fsm = StateMachine(debounce_ms=1)
    fsm.update(Perception(green_right=True))
    time.sleep(0.05)  # > tick timer Windows (~15.6ms), rende il debounce deterministico
    assert fsm.update(Perception(green_right=True)) == State.VERDE_DX


def test_finish_action_returns_to_seguilinea():
    from src.state_machine import State

    fsm = _fsm()
    fsm.state = State.OSTACOLO
    assert fsm.finish_action() == State.SEGUILINEA
