"""Video job registry tests (no model / no video files required)."""

from services.video_service import JobStore


def test_job_store_roundtrip():
    store = JobStore()
    job = store.create("detect", "clip.mp4", {"conf": 0.25})
    assert store.get(job.job_id) is job
    jobs = store.list()
    assert jobs and jobs[0].job_id == job.job_id
    data = job.to_dict()
    assert data["status"] == "queued"
    assert data["kind"] == "detect"
    assert data["output"] is None


def test_job_store_filters():
    store = JobStore()
    detect_job = store.create("detect", "a.mp4", {})
    track_job = store.create("track", "b.mp4", {})
    assert [j.job_id for j in store.list(kind="track")] == [track_job.job_id]
    assert [j.job_id for j in store.list(kind="detect")] == [detect_job.job_id]
    assert store.get("missing") is None
