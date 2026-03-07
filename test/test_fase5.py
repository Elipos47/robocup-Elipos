# ===========================================================================
# test_fase5.py – Test suite per versione con giroscopio
# ===========================================================================
# Test per verificare:
# 1. Interfaccia giroscopio (simulazione)
# 2. Turn precisi
# 3. Stuck detection
# 4. Integrazione con LogicController
# ===========================================================================

import sys
import time
from pathlib import Path

# Aggiungi parent directory al path
sys.path.insert(0, str(Path(__file__).parent))

from gyroscope_interface import (
    GyroscopeInterface, Orientation, MotionData, 
    StuckDetector, get_gyro, wait_for_calibration
)
from state_machine import current_state, RobotState
from timer import timer
from logic_controller import LogicController
from line_detector import LineDetection
from color_detector import ColorDetection


def test_gyroscope_interface():
    """Test interfaccia giroscopio in modalità simulazione."""
    print("\n" + "="*60)
    print("TEST 1: Interfaccia Giroscopio")
    print("="*60)
    
    # Crea istanza in simulazione
    gyro = GyroscopeInterface(use_simulation=True)
    
    print(f"Connesso: {gyro.is_connected}")
    print(f"Simulazione: {gyro.is_simulation}")
    print(f"Calibrazione: {gyro.calibration_status}")
    
    # Avvia
    gyro.start()
    time.sleep(0.2)  # Attendi letture
    
    # Leggi orientamento
    orient = gyro.orientation
    print(f"Orientamento: Yaw={orient.yaw:.1f}°, Pitch={orient.pitch:.1f}°, Roll={orient.roll:.1f}°")
    
    # Test set simulato
    gyro.set_simulated_orientation(yaw=90.0, pitch=0.0, roll=0.0)
    time.sleep(0.1)
    yaw = gyro.get_yaw()
    print(f"Yaw impostato a 90°: {yaw:.1f}°")
    assert 85 <= yaw <= 95, f"Yaw dovrebbe essere circa 90, è {yaw}"
    
    # Test turn direction
    gyro.set_simulated_orientation(yaw=0.0)
    direction = gyro.calculate_turn_direction(90.0)
    print(f"Da 0° a 90°: direzione {direction}")
    assert direction == 'cw', "Dovrebbe essere cw (clockwise)"
    
    direction = gyro.calculate_turn_direction(270.0)
    print(f"Da 0° a 270°: direzione {direction}")
    assert direction == 'ccw', "Dovrebbe essere ccw (counter-clockwise)"
    
    # Test turn to angle
    gyro.set_simulated_orientation(yaw=45.0)
    reached = gyro.turn_to_angle(45.0, tolerance=5.0)
    print(f"Turn to 45° (già lì): {reached}")
    assert reached, "Dovrebbe essere True"
    
    gyro.stop()
    print("✅ Test giroscopio completato")


def test_stuck_detector():
    """Test stuck detector."""
    print("\n" + "="*60)
    print("TEST 2: Stuck Detector")
    print("="*60)
    
    detector = StuckDetector(history_size=10)
    
    # Simula movimento normale
    print("Simulazione movimento normale...")
    for i in range(5):
        orient = Orientation(yaw=i*5, pitch=0, roll=0)  # Cambia yaw
        motion = MotionData(
            linear_accel=(0.1, 0.0, 9.8),
            gyro=(0, 0, 5),
            gravity=(0, 0, 9.8)
        )
        detector.update(orient, motion)
        time.sleep(0.05)
    
    print(f"Is stuck: {detector.is_stuck}")
    assert not detector.is_stuck, "Non dovrebbe essere bloccato"
    
    # Simula stuck (accelerazione ma nessun cambio orientamento)
    print("Simulazione STUCK...")
    for i in range(25):
        orient = Orientation(yaw=0, pitch=0, roll=0)  # Stesso yaw
        motion = MotionData(
            linear_accel=(0.5, 0.0, 9.8),  # C'è accelerazione
            gyro=(0, 0, 0),
            gravity=(0, 0, 9.8)
        )
        detector.update(orient, motion)
    
    print(f"Is stuck: {detector.is_stuck}")
    print(f"Stuck frames: {detector.stuck_frames}")
    assert detector.is_stuck, "Dovrebbe essere bloccato"
    
    # Reset
    detector.reset()
    print(f"Dopo reset - Is stuck: {detector.is_stuck}")
    assert not detector.is_stuck, "Dopo reset non dovrebbe essere bloccato"
    
    print("✅ Test stuck detector completato")


def test_precise_turns():
    """Test turn precisi nel LogicController."""
    print("\n" + "="*60)
    print("TEST 3: Turn Precisi")
    print("="*60)
    
    logic = LogicController()
    gyro = get_gyro()
    gyro.start()
    
    # Test 1: Turn di 90°
    print("Test turn 90°...")
    gyro.set_simulated_orientation(yaw=0.0)
    cmd = logic.start_precise_turn(90.0)
    print(f"Comando iniziale: {cmd}")
    
    # Simula il turn
    for yaw in [10, 30, 60, 85, 95]:
        gyro.set_simulated_orientation(yaw=float(yaw))
        time.sleep(0.05)
        cmd = logic._execute_precise_turn()
        print(f"  Yaw={yaw}° -> Comando: {cmd}")
    
    # Dovrebbe essere arrivato
    assert logic._turn_target_angle is None, "Turn dovrebbe essere completato"
    
    # Test 2: Turn di -45° (sinistra)
    print("\nTest turn -45°...")
    gyro.set_simulated_orientation(yaw=90.0)
    cmd = logic.start_precise_turn(-45.0)
    print(f"Target: {logic._turn_target_angle:.1f}°")
    
    # Simula turn a sinistra
    for yaw in [80, 60, 50, 45]:
        gyro.set_simulated_orientation(yaw=float(yaw))
        time.sleep(0.05)
        cmd = logic._execute_precise_turn()
        print(f"  Yaw={yaw}° -> Comando: {cmd}")
    
    print("✅ Test turn precisi completato")


def test_stuck_recovery():
    """Test recovery da stuck."""
    print("\n" + "="*60)
    print("TEST 4: Stuck Recovery")
    print("="*60)
    
    logic = LogicController()
    gyro = get_gyro()
    
    # Simula stuck
    print("Simulazione stuck e recovery...")
    logic._stuck_recovery_attempts = 0
    
    # Primo tentativo: backup
    cmd = logic._handle_stuck_recovery()
    print(f"Tentativo 1: {cmd}")
    assert cmd == "ind", "Primo tentativo dovrebbe essere indietro"
    
    # Secondo tentativo: turn 90°
    gyro.set_simulated_orientation(yaw=0.0)
    cmd = logic._handle_stuck_recovery()
    print(f"Tentativo 2: {cmd}")
    assert cmd in ["cd", "cs"], "Secondo tentativo dovrebbe essere turn"
    
    # Terzo tentativo: turn -90°
    cmd = logic._handle_stuck_recovery()
    print(f"Tentativo 3: {cmd}")
    assert cmd in ["cd", "cs"], "Terzo tentativo dovrebbe essere turn"
    
    # Quarto tentativo: give up
    cmd = logic._handle_stuck_recovery()
    print(f"Tentativo 4: {cmd}")
    assert cmd == "S", "Quarto tentativo dovrebbe essere stop"
    
    print("✅ Test stuck recovery completato")


def test_integration_with_logic():
    """Test integrazione completa."""
    print("\n" + "="*60)
    print("TEST 5: Integrazione Completa")
    print("="*60)
    
    logic = LogicController()
    gyro = get_gyro()
    gyro.start()
    
    # Crea dati di test
    line_det = LineDetection()
    line_det.line_detected = True
    line_det.line_angle = 5
    line_det.has_center = True
    
    color_det = ColorDetection()
    color_det.green_left = False
    color_det.green_right = False
    color_det.red_detected = False
    
    # Test 1: Funzionamento normale
    print("Test funzionamento normale...")
    gyro.set_simulated_orientation(yaw=0.0)
    cmd = logic.decide(line_det, color_det, False, 999, None)
    print(f"Comando: {cmd}")
    assert cmd in ["A", "gd", "gs"]
    
    # Test 2: Verifica che giroscopio venga controllato in STOP
    print("\nTest stato STOP con giroscopio...")
    current_state.reset(RobotState.STOP)
    line_det.line_detected = False
    
    # Non stuck
    for _ in range(5):
        orient = Orientation(yaw=10, pitch=0, roll=0)
        motion = MotionData((0,0,9.8), (0,0,0), (0,0,9.8))
        gyro.stuck_detector.update(orient, motion)
    
    cmd = logic.decide(line_det, color_det, False, 999, None)
    print(f"Comando in STOP (non stuck): {cmd}")
    
    # Simula stuck
    print("\nTest stato STOP con stuck...")
    for _ in range(25):
        orient = Orientation(yaw=0, pitch=0, roll=0)
        motion = MotionData((0.5,0,9.8), (0,0,0), (0,0,9.8))
        gyro.stuck_detector.update(orient, motion)
    
    print(f"Stuck rilevato: {gyro.stuck_detector.is_stuck}")
    
    print("✅ Test integrazione completato")


def test_gyro_status():
    """Test funzioni di stato giroscopio."""
    print("\n" + "="*60)
    print("TEST 6: Stato Giroscopio")
    print("="*60)
    
    gyro = get_gyro()
    gyro.start()
    
    # Test is_level
    gyro.set_simulated_orientation(yaw=0, pitch=0, roll=0)
    level = gyro.is_level(tolerance=3.0)
    print(f"Livello (0,0,0): {level}")
    assert level, "Dovrebbe essere livellato"
    
    gyro.set_simulated_orientation(yaw=0, pitch=10, roll=0)
    level = gyro.is_level(tolerance=3.0)
    print(f"Livello (0,10,0): {level}")
    assert not level, "Non dovrebbe essere livellato con pitch=10"
    
    # Test get_status_dict
    status = gyro.get_status_dict()
    print(f"\nStatus completo:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    assert 'yaw' in status
    assert 'pitch' in status
    assert 'roll' in status
    assert 'calibrated' in status
    
    print("✅ Test stato giroscopio completato")


def run_all_tests():
    """Esegue tutti i test."""
    print("\n" + "="*70)
    print("  TEST SUITE FASE 5 - Giroscopio BNO055")
    print("="*70)
    
    try:
        test_gyroscope_interface()
        test_stuck_detector()
        test_precise_turns()
        test_stuck_recovery()
        test_integration_with_logic()
        test_gyro_status()
        
        print("\n" + "="*70)
        print("  ✅ TUTTI I TEST FASE 5 COMPLETATI CON SUCCESSO")
        print("="*70)
        
        return True
        
    except AssertionError as e:
        print("\n" + "="*70)
        print(f"  ❌ TEST FALLITO: {e}")
        print("="*70)
        return False
        
    except Exception as e:
        print("\n" + "="*70)
        print(f"  ❌ ERRORE: {e}")
        print("="*70)
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            gyro = get_gyro()
            gyro.stop()
        except:
            pass


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
