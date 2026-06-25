import irsdk
import time

ir = irsdk.IRSDK()
last_positions = {}

def driver_name(car_idx):
    if car_idx == 0:
        return "Tim Lee"
    return f"AI Driver {car_idx}"

print("=" * 60)
print("RGC AI Broadcaster - Pass Detector")
print("=" * 60)

while True:
    if ir.startup():
        print("\nConnected to iRacing!")

        while ir.is_initialized and ir.is_connected:
            session_info = ir["SessionInfo"]
            current_session = session_info["CurrentSessionNum"]
            session = session_info["Sessions"][current_session]
            results = session.get("ResultsPositions") or []

            current_positions = {}

            for car in results:
                car_idx = car.get("CarIdx")
                position = car.get("Position")
                current_positions[car_idx] = position

                old_position = last_positions.get(car_idx)

                if old_position is not None and position < old_position:
                    print(
                        f"PASS DETECTED: {driver_name(car_idx)} moved "
                        f"from P{old_position} to P{position}"
                    )

            last_positions = current_positions

            time.sleep(2)

    else:
        print("Waiting for iRacing...")
        time.sleep(5)