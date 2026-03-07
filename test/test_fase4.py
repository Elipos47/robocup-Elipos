# ===========================================================================
# test_fase4.py – Test integrazione FASE 4
# ===========================================================================
# Test per verificare:
# 1. Logging avanzato
# 2. Integrazione gap detection
# 3. Transizioni stato corrette
# 4. Recovery da STOP
# ===========================================================================

import sys
import time
from pathlib import Path

# Aggiungi parent directory al path
sys.path.insert(0, str(Path(__file__).parent))

from state_machine import current_state, RobotState
from timer import timer
from logger import main_logger, get_logger, RobotLogger
from gap_detector import gap_detector, GapInfo, GapDetector
from logic_controller import LogicController
from line_detector import LineDetection
from color_detector import ColorDetection


def test_logger():
    """Test sistema di logging."""
    print("\n" + "="*60)
    print("TEST 1: Sistema di Logging")
    print("="*60)
    
    # Test livelli
    logger = get_logger("TEST")
    logger.debug("Messaggio debug")
    logger.info("Messaggio info")
    logger.warning("Messaggio warning")
    logger.error("Messaggio error")
    
    # Test metodi speciali
    logger.state_transition("LINE_DETECTED", "GAP_DETECTED", "test")
    logger.command_sent("A", {"speed": 0.5})
    logger.sensor_reading("distance", 15.5)
    
    # Test stati
    stats = logger.get_stats()
    print(f"Statistiche logger: {stats}")
    
    # Test recent logs
    logs = logger.get_recent_logs(5)
    print(f"Ultimi {len(logs)} log in memoria")
    
    print("✅ Test logging completato")


def test_gap_detector():
    """Test gap detector."""
    print("\n" + "="*60)
    print("TEST 2: Gap Detector")
    print("="*60)
    
    # Reset
    gap_detector.reset()
    
    # Test GapInfo
    gap_info = GapInfo(
        detected=True,
        validated=True,
        angle=45.0,
        center_x=100,
        center_y=200,
        confidence=0.85,
        width=50,
        height=30,
        area=1500
    )
    
    print(f"GapInfo creato: detected={gap_info.detected}, "
          f"angle={gap_info.angle}, confidence={gap_info.confidence}")
    
    # Test orientamento
    gap_detector.start_orientation()
    print("Orientamento avviato")
    
    # Test crossing
    gap_detector.start_crossing()
    print("Attraversamento avviato")
    
    # Verifica stato
    print(f"Crossing active: {gap_detector._crossing_active}")
    print(f"Orientation phase: {gap_detector._orientation_phase}")
    
    print("✅ Test gap detector completato")


def test_state_transitions():
    """Test transizioni di stato."""
    print("\n" + "="*60)
    print("TEST 3: Transizioni di Stato")
    print("="*60)
    
    # Reset stato
    current_state.reset(RobotState.LINE_DETECTED)
    print(f"Stato iniziale: {current_state.state_name}")
    
    # Test transizioni
    transitions = [
        (RobotState.GAP_DETECTED, "gap_found"),
        (RobotState.GAP_AVOID, "gap_validated"),
        (RobotState.LINE_DETECTED, "line_reacquired"),
        (RobotState.OBSTACLE_DETECTED, "obstacle_found"),
        (RobotState.OBSTACLE_AVOID, "avoiding"),
        (RobotState.LINE_DETECTED, "obstacle_cleared"),
        (RobotState.STOP, "emergency"),
        (RobotState.LINE_DETECTED, "reset"),
    ]
    
    for new_state, reason in transitions:
        old_state = current_state.state_name
        current_state.transition_to(new_state, reason)
        print(f"  {old_state} -> {new_state.name} (reason: {reason})")
        time.sleep(0.1)
    
    # Test history
    history = current_state.get_transitions_history(5)
    print(f"\nUltime {len(history)} transizioni:")
    for t in history:
        print(f"  {t.from_state.name} -> {t.to_state.name}")
    
    print("✅ Test transizioni completato")


def test_logic_controller():
    """Test LogicController con gap detection."""
    print("\n" + "="*60)
    print("TEST 4: LogicController + Gap Detection")
    print("="*60)
    
    # Inizializza
    logic = LogicController()
    print(f"Stato iniziale: {logic.current_state_name}")
    
    # Crea dati di test
    line_det = LineDetection()
    line_det.line_detected = True
    line_det.line_angle = 10
    line_det.has_center = True
    
    color_det = ColorDetection()
    color_det.green_left = False
    color_det.green_right = False
    color_det.red_detected = False
    
    # Test 1: Linea rilevata
    cmd = logic.decide(line_det, color_det, False, 999, None)
    print(f"Linea rilevata -> Comando: {cmd}")
    assert cmd in ["A", "gd", "gs"], f"Comando inatteso: {cmd}"
    
    # Test 2: Gap rilevato
    gap_info = GapInfo(
        detected=True,
        validated=True,
        angle=0,
        confidence=0.9
    )
    line_det.line_detected = False
    cmd = logic.decide(line_det, color_det, False, 999, gap_info)
    print(f"Gap rilevato -> Comando: {cmd}, Stato: {logic.current_state_name}")
    
    # Test 3: Linea persa senza gap
    gap_info = GapInfo(detected=False)
    for i in range(6):
        cmd = logic.decide(line_det, color_det, False, 999, gap_info)
    print(f"Linea persa (6 frame) -> Comando: {cmd}, Stato: {logic.current_state_name}")
    assert cmd == "S", f"Dovrebbe essere STOP, invece è: {cmd}"
    
    # Test 4: Recovery
    line_det.line_detected = True
    cmd = logic.decide(line_det, color_det, False, 999, None)
    print(f"Linea ripresa -> Comando: {cmd}, Stato: {logic.current_state_name}")
    assert logic.current_state_name == "LINE_DETECTED"
    
    # Test 5: Ostacolo
    line_det.line_detected = True
    cmd = logic.decide(line_det, color_det, True, 10, None)
    print(f"Ostacolo rilevato -> Comando: {cmd}, Stato: {logic.current_state_name}")
    assert cmd == "obj"
    
    # Test 6: Rosso
    color_det.red_detected = True
    line_det.line_detected = True
    cmd = logic.decide(line_det, color_det, False, 999, None)
    print(f"Rosso rilevato -> Comando: {cmd}, Stato: {logic.current_state_name}")
    assert cmd == "S"
    
    # Reset
    logic.reset()
    print(f"Dopo reset -> Stato: {logic.current_state_name}")
    
    print("✅ Test LogicController completato")


def test_timer_integration():
    """Test integrazione timer."""
    print("\n" + "="*60)
    print("TEST 5: Timer Integration")
    print("="*60)
    
    # Reset timer
    timer.clear_all()
    
    # Test timer
    timer.set_timer("test1", 0.5)
    timer.set_timer("test2", 1.0)
    
    print(f"Timer attivi: {timer.list_timers()}")
    print(f"Remaining test1: {timer.get_remaining('test1'):.2f}s")
    
    # Attendi
    time.sleep(0.6)
    
    print(f"test1 scaduto? {timer.get_timer('test1')}")
    print(f"test2 scaduto? {timer.get_timer('test2')}")
    print(f"Remaining test2: {timer.get_remaining('test2'):.2f}s")
    
    timer.clear_all()
    print("✅ Test timer completato")


def run_all_tests():
    """Esegue tutti i test."""
    print("\n" + "="*70)
    print("  TEST SUITE FASE 4 - Logging + Gap Detection + Controllo")
    print("="*70)
    
    try:
        test_logger()
        test_gap_detector()
        test_state_transitions()
        test_logic_controller()
        test_timer_integration()
        
        print("\n" + "="*70)
        print("  ✅ TUTTI I TEST COMPLETATI CON SUCCESSO")
        print("="*70)
        
        # Esporta log
        main_logger.export_to_json("logs/test_fase4_results.json")
        print("\nRisultati esportati in: logs/test_fase4_results.json")
        
        return True
        
    except Exception as e:
        print("\n" + "="*70)
        print(f"  ❌ TEST FALLITO: {e}")
        print("="*70)
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        main_logger.close()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
