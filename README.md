# OT-2 REST Wrapper

REST API that wraps [PyLabRobot](https://github.com/PyLabRobot/pylabrobot) to control an OpenTrons OT-2 liquid handler over HTTP.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Running

```bash
uvicorn app.main:app --reload
```

The Swagger UI is available at `http://localhost:8000/docs`.

## Configuration

Settings are loaded from environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `OT2_HOST` | `localhost` | Robot IP address |
| `OT2_PORT` | `31950` | Robot HTTP API port |
| `OT2_TRAVERSAL_HEIGHT` | `120.0` | Safe travel height in mm |
| `DECK_CONFIG_PATH` | — | Path to a YAML deck layout file |

### Deck config file

A YAML file can pre-load deck resources at connect time. See [`config.example.yaml`](config.example.yaml):

```yaml
robot:
  host: "192.168.0.61"
  traversal_height: 120

deck:
  - slot: 9
    type: tip_rack
    ot_name: "opentrons_96_filtertiprack_20ul"
    name: "20uL Tip Rack 1"

  - slot: 6
    type: plate
    ot_name: "corning_96_wellplate_360ul_flat"
    name: "premixplate"

  - slot: 4
    type: tube_rack
    ot_name: "opentrons_24_aluminumblock_nest_1.5ml_snapcap"
    name: "tube_rack"
```

Resource types:
- **tip_rack** / **plate** — any name from the [Opentrons labware library](https://github.com/Opentrons/opentrons/tree/edge/shared-data/labware)
- **tube_rack** — Opentrons tube rack or aluminum block definitions

## API Endpoints

### Robot

| Method | Path | Description |
|---|---|---|
| `POST` | `/robot/connect` | Connect to OT-2 (body can override host/port/traversal_height) |
| `POST` | `/robot/disconnect` | Disconnect and clear state |
| `POST` | `/robot/home` | Home the robot |
| `GET` | `/robot/status` | Connection status |

### Deck

| Method | Path | Description |
|---|---|---|
| `GET` | `/deck` | List all 12 deck slots |
| `POST` | `/deck/slots/{id}/tip-rack` | Assign a tip rack |
| `POST` | `/deck/slots/{id}/plate` | Assign a well plate |
| `POST` | `/deck/slots/{id}/tube-rack` | Assign a tube rack / aluminum block |
| `DELETE` | `/deck/slots/{id}` | Remove a resource from a slot |

### Commands

| Method | Path | Description |
|---|---|---|
| `POST` | `/commands/pick-up-tips` | Pick up tips |
| `POST` | `/commands/drop-tips` | Drop tips (to resource or trash) |
| `POST` | `/commands/return-tips` | Return tips to original positions |
| `POST` | `/commands/aspirate` | Aspirate from wells |
| `POST` | `/commands/dispense` | Dispense into wells |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |

## Usage Example

A typical workflow using `curl`:

```bash
# 1. Connect to the robot
curl -X POST http://localhost:8000/robot/connect \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.0.61"}'

# 2. Assign labware to deck slots
curl -X POST http://localhost:8000/deck/slots/9/tip-rack \
  -H "Content-Type: application/json" \
  -d '{"ot_name": "opentrons_96_filtertiprack_20ul", "name": "tips"}'

curl -X POST http://localhost:8000/deck/slots/6/plate \
  -H "Content-Type: application/json" \
  -d '{"resource_type": "corning_96_wellplate_360ul_flat", "name": "plate"}'

# 3. Pick up a tip (well index 0 = A1)
curl -X POST http://localhost:8000/commands/pick-up-tips \
  -H "Content-Type: application/json" \
  -d '{"resource_name": "tips", "well_indices": [0]}'

# 4. Aspirate 100 uL from well A1
curl -X POST http://localhost:8000/commands/aspirate \
  -H "Content-Type: application/json" \
  -d '{"resource_name": "plate", "well_indices": [0], "volumes": [100.0]}'

# 5. Dispense 100 uL into well B1
curl -X POST http://localhost:8000/commands/dispense \
  -H "Content-Type: application/json" \
  -d '{"resource_name": "plate", "well_indices": [1], "volumes": [100.0]}'

# 6. Drop tips to trash
curl -X POST http://localhost:8000/commands/drop-tips \
  -H "Content-Type: application/json" \
  -d '{}'

# 7. Disconnect
curl -X POST http://localhost:8000/robot/disconnect
```

All command endpoints accept optional `offsets` (list of `{x, y, z}` in mm) for fine position adjustment, and aspirate/dispense accept optional `flow_rates` (in uL/s).
