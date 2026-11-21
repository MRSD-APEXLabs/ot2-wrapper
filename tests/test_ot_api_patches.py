"""Tests for app.ot_api_patches — HTTP timeout, poll rate limit, command-status logging."""

import socket
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

import ot_api.requestor as requestor
import ot_api.runs as runs
from ot_api.decorators import OTError

import app.ot_api_patches as patches


@pytest.fixture(autouse=True)
def _clear_polls():
    patches._polls.clear()
    yield
    patches._polls.clear()


def test_patches_installed():
    assert requestor.make_request is patches._make_request
    assert requestor.post is patches._logged_post
    assert runs.get_command is patches._get_command


class TestMakeRequest:
    def _req(self):
        return urllib.request.Request("http://ot2:31950/runs/r/commands/c", method="GET")

    def test_passes_timeout_and_parses_json(self):
        resp = MagicMock()
        resp.read.return_value = b'{"data": {"status": "succeeded"}}'
        resp.__enter__.return_value = resp
        with patch("urllib.request.urlopen", return_value=resp) as urlopen:
            assert patches._make_request(self._req()) == {"data": {"status": "succeeded"}}
        assert urlopen.call_args.kwargs["timeout"] == patches.HTTP_TIMEOUT_S

    @pytest.mark.parametrize("exc", [socket.timeout("timed out"),
                                     urllib.error.URLError(socket.timeout("timed out"))])
    def test_timeout_raises_oterror(self, exc):
        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(OTError, match="did not answer GET"):
                patches._make_request(self._req())

    def test_connection_refused_propagates(self):
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError(ConnectionRefusedError())):
            with pytest.raises(urllib.error.URLError):
                patches._make_request(self._req())


class TestGetCommand:
    def _result(self, status):
        return {"data": {"status": status, "commandType": "aspirateInPlace"}}

    def test_sleeps_between_polls_not_before_first(self):
        statuses = iter(["running", "running", "succeeded"])
        with patch.object(patches, "_orig_get_command",
                          side_effect=lambda cid, **kw: self._result(next(statuses))), \
             patch("time.sleep") as sleep:
            patches._get_command("c1", run_id="r")
            assert sleep.call_count == 0
            patches._get_command("c1", run_id="r")
            patches._get_command("c1", run_id="r")
        assert sleep.call_count == 2
        assert "c1" not in patches._polls  # forgotten once terminal

    def test_logs_status_changes_only(self, caplog):
        statuses = iter(["running", "running", "succeeded"])
        with patch.object(patches, "_orig_get_command",
                          side_effect=lambda cid, **kw: self._result(next(statuses))), \
             patch("time.sleep"), caplog.at_level("INFO", logger=patches.__name__):
            for _ in range(3):
                patches._get_command("c1", run_id="r")
        changes = [r.getMessage() for r in caplog.records if "→" in r.getMessage()]
        assert len(changes) == 2
        assert "None → running" in changes[0] and "running → succeeded" in changes[1]

    def test_forwards_run_id(self):
        with patch.object(patches, "_orig_get_command",
                          return_value=self._result("succeeded")) as orig:
            patches._get_command("c1", run_id="r9")
        orig.assert_called_once_with("c1", run_id="r9")
