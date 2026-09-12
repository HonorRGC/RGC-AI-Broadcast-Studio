import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from broadcaster.telemetry import IRacingTelemetry
from replay.telemetry_snapshot import TelemetrySnapshot


def parse_args():
    parser = argparse.ArgumentParser(description="Record iRacing telemetry as JSONL")
    parser.add_argument("output", type=Path, help="Destination JSONL file")
    parser.add_argument("--interval", type=float, default=1.0)
    return parser.parse_args()


def main():
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    telemetry = IRacingTelemetry()

    print("Waiting for iRacing...")
    while not telemetry.startup():
        time.sleep(2)

    print(f"Recording to {args.output}. Press Ctrl+C to stop.")
    try:
        with args.output.open("a", encoding="utf-8") as recording:
            while telemetry.is_connected():
                snapshot = TelemetrySnapshot.from_telemetry(
                    telemetry,
                    timestamp=time.time(),
                )
                recording.write(json.dumps(snapshot.to_dict(), separators=(",", ":")) + "\n")
                recording.flush()
                time.sleep(max(args.interval, 0.1))
    except KeyboardInterrupt:
        print("Recording stopped.")


if __name__ == "__main__":
    main()
