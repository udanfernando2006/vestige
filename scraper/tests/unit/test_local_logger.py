import json
from pathlib import Path

import pytest
from storage import local_logger


@pytest.fixture
def log_dir(tmp_path):
    return str(tmp_path)


# ---------------------------------------------------------------------------
# build_log_path
# ---------------------------------------------------------------------------


class TestBuildLogPath:

    def test_path_structure(self, log_dir):
        run_id = "2026-05-16T08:00:00Z"
        path = local_logger.build_log_path(run_id, log_dir=log_dir)
        # Expect logs/<year>/<month>/<day>/<time>.json
        parts = Path(path).parts
        assert "2026" in parts
        assert "05" in parts
        assert "16" in parts
        assert path.endswith(".json")

    def test_returns_string(self, log_dir):
        path = local_logger.build_log_path("2026-01-01T00:00:00Z", log_dir=log_dir)
        assert isinstance(path, str)

    def test_different_timestamps_produce_different_paths(self, log_dir):
        path_a = local_logger.build_log_path("2026-05-16T08:00:00Z", log_dir=log_dir)
        path_b = local_logger.build_log_path("2026-05-16T14:00:00Z", log_dir=log_dir)
        assert path_a != path_b


# ---------------------------------------------------------------------------
# write_run_log
# ---------------------------------------------------------------------------


SAMPLE_RUN = {
    "run_id": "2026-05-16T08:00:00Z",
    "total_pairs": 3,
    "results": [],
    "changes": [],
    "needs_setup": [],
    "errors": [],
    "duration_seconds": 12.4,
}


class TestWriteRunLog:

    def test_creates_file(self, log_dir):
        local_logger.write_run_log(SAMPLE_RUN, log_dir=log_dir)
        log_path = local_logger.build_log_path(SAMPLE_RUN["run_id"], log_dir=log_dir)
        assert Path(log_path).exists()

    def test_written_content_is_valid_json(self, log_dir):
        local_logger.write_run_log(SAMPLE_RUN, log_dir=log_dir)
        log_path = local_logger.build_log_path(SAMPLE_RUN["run_id"], log_dir=log_dir)
        content = json.loads(Path(log_path).read_text(encoding="utf-8"))
        assert content["run_id"] == SAMPLE_RUN["run_id"]

    def test_creates_parent_directories(self, log_dir):
        local_logger.write_run_log(SAMPLE_RUN, log_dir=log_dir)
        log_path = Path(local_logger.build_log_path(SAMPLE_RUN["run_id"], log_dir=log_dir))
        assert log_path.parent.is_dir()

    def test_idempotent_on_repeat_write(self, log_dir):
        # Running the same summary twice should overwrite, not error
        local_logger.write_run_log(SAMPLE_RUN, log_dir=log_dir)
        local_logger.write_run_log(SAMPLE_RUN, log_dir=log_dir)
        log_path = local_logger.build_log_path(SAMPLE_RUN["run_id"], log_dir=log_dir)
        assert Path(log_path).exists()