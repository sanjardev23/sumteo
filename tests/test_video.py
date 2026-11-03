import cv2
import numpy as np
import pytest

from sumteo.video.source import VideoSource


def _write_video(path, n_frames: int, fps: float) -> str:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for i in range(n_frames):
        writer.write(np.full((48, 64, 3), i % 256, dtype=np.uint8))
    writer.release()
    return str(path)


def test_file_timestamps_come_from_frame_index(tmp_path):
    frames = list(VideoSource(_write_video(tmp_path / "v.mp4", 30, fps=10)).frames())
    assert [f.index for f in frames] == list(range(30))
    assert frames[15].ts == pytest.approx(1.5)


def test_target_fps_skips_frames_evenly(tmp_path):
    frames = list(VideoSource(_write_video(tmp_path / "v.mp4", 30, fps=30), target_fps=10).frames())
    assert [f.index for f in frames] == list(range(0, 30, 3))
    assert frames[-1].ts == pytest.approx(27 / 30)


def test_target_fps_above_native_keeps_every_frame(tmp_path):
    frames = list(VideoSource(_write_video(tmp_path / "v.mp4", 10, fps=10), target_fps=25).frames())
    assert len(frames) == 10


def test_missing_source_raises():
    with pytest.raises(RuntimeError):
        next(VideoSource("data/raw/does_not_exist.mp4").frames())


def test_a_looping_file_keeps_the_clock_running(tmp_path):
    source = VideoSource(_write_video(tmp_path / "v.mp4", 10, fps=10), loop=True)
    frames = [f for _, f in zip(range(25), source.frames())]
    assert [f.index for f in frames] == list(range(25))
    assert frames[24].ts == pytest.approx(2.4)
    assert np.array_equal(frames[10].image, frames[0].image)       # second pass starts at the first frame
