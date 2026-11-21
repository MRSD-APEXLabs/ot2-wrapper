"""Runtime patches to ot_api, the library PLR uses to talk to the OT-2 robot-server.

- Log every raw POST body and fix ot_api's dispense_in_place bug (it sends "aspirateInPlace").
- Give each HTTP call to the OT-2 a timeout. ot_api's urlopen has none, so a robot-server that
  never answers hangs the request (and, as handlers block the event loop, the whole wrapper).
- Rate-limit ot_api's command polling. Its wait loop re-polls with no sleep, hammering the
  robot-server's Pi while a command runs.
- Log each command's status changes with elapsed time, so a slow or stuck command is visible.

Import this module once (app.state does) before any ot_api call.
"""

import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request

import ot_api.requestor as requestor
import ot_api.runs as runs
from ot_api.decorators import OTError

logger = logging.getLogger(__name__)

HTTP_TIMEOUT_S = float(os.environ.get("OT2_HTTP_TIMEOUT_S", "30"))
POLL_INTERVAL_S = float(os.environ.get("OT2_POLL_INTERVAL_S", "0.1"))
SLOW_CALL_S = 2.0

_orig_post = requestor.post
_orig_get_command = runs.get_command

# command_id → {"start": monotonic time of first poll, "status": last status seen}
_polls: dict[str, dict] = {}


def _logged_post(path: str, data=None):
    if data is not None:
        cmd = data.get("data", {})
        if cmd.get("commandType") == "aspirateInPlace" and "pushOut" in cmd.get("params", {}):
            cmd["commandType"] = "dispenseInPlace"
            logger.warning("ot_api bug: corrected aspirateInPlace → dispenseInPlace")
        logger.info("OT-2 HTTP POST %s body=%s", path, json.dumps(data))
    return _orig_post(path, data)


def _make_request(req) -> dict:
    """ot_api.requestor.make_request with a timeout and slow-call logging."""
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        raise Exception(e.read().decode())
    except (socket.timeout, TimeoutError) as e:
        logger.error("OT-2 HTTP %s %s: no answer in %.0fs", req.get_method(), req.full_url,
                     HTTP_TIMEOUT_S)
        raise OTError(f"OT-2 did not answer {req.get_method()} {req.full_url} "
                      f"within {HTTP_TIMEOUT_S:.0f}s") from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            logger.error("OT-2 HTTP %s %s: no answer in %.0fs", req.get_method(), req.full_url,
                         HTTP_TIMEOUT_S)
            raise OTError(f"OT-2 did not answer {req.get_method()} {req.full_url} "
                          f"within {HTTP_TIMEOUT_S:.0f}s") from e
        raise
    elapsed = time.monotonic() - start
    if elapsed > SLOW_CALL_S:
        logger.warning("OT-2 HTTP %s %s took %.1fs", req.get_method(), req.full_url, elapsed)
    return json.loads(body)


def _get_command(command_id: str, run_id=None, **kwargs):
    """Poll one command, sleeping between polls and logging its status changes."""
    seen = _polls.get(command_id)
    if seen is None:
        seen = _polls[command_id] = {"start": time.monotonic(), "status": None}
    else:
        time.sleep(POLL_INTERVAL_S)
    if run_id is not None:
        kwargs["run_id"] = run_id
    result = _orig_get_command(command_id, **kwargs)

    data = result.get("data", {})
    status = data.get("status")
    if status != seen["status"]:
        logger.info("OT-2 command %s %s: %s → %s after %.1fs", data.get("commandType", "?"),
                    command_id, seen["status"], status, time.monotonic() - seen["start"])
        seen["status"] = status
    if status not in ("queued", "running"):
        _polls.pop(command_id, None)
    return result


requestor.post = _logged_post
requestor.make_request = _make_request
runs.get_command = _get_command
