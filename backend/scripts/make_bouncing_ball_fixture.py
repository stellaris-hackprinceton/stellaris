"""SIMULATED bouncing-ball video fixture (test data only — never observed evidence).

Run inside the worker image (it has OpenCV and PyAV); the MP4 bytes go to stdout:

    docker run --rm -i --network none --read-only --tmpfs /tmp:size=64m \
        --entrypoint python stellaris-worker:dev -I - < scripts/make_bouncing_ball_fixture.py > SIMULATED.mp4

The host-side test imports only the constants and ground_truth() below (stdlib only), so
the expected heights come from the same definitions that rendered the video.

Physics: a ball of radius RADIUS_PX in free flight with G_PX_S2 downward acceleration,
apex heights (rise of the ball centre above its centre at impact) HEIGHT_1_PX * RATIO**k,
i.e. coefficient of restitution sqrt(RATIO). The first apex is at FIRST_APEX_S.
Rendered with sub-pixel (1/16 px) anti-aliased circles on a uniform background.
"""

import math

WIDTH, HEIGHT, FPS, DURATION_S = 480, 360, 60, 3.6
RADIUS_PX = 12
GROUND_CENTER_Y = 320.0          # image y of the ball centre at impact
G_PX_S2 = 2000.0
HEIGHT_1_PX = 280.0
RATIO = 0.64
FIRST_APEX_S = 0.15
X0_PX, VX_PX_S = 60.0, 60.0
BACKGROUND_BGR = (60, 60, 60)
BALL_BGR = (40, 140, 255)
FLOOR_BGR = (150, 150, 150)
# Reference length drawn on the floor for the calibrated run: 400 px == 2.0 m (fixture truth).
REF_A_PX, REF_B_PX, REF_LENGTH_M = (40.0, 340.0), (440.0, 340.0), 2.0


def ground_truth():
    """Apex times and heights (px) whose apex lies inside [0, DURATION_S] with both sides visible."""
    apexes, t_apex, k = [], FIRST_APEX_S, 0
    while True:
        h = HEIGHT_1_PX * RATIO ** k
        half = math.sqrt(2 * h / G_PX_S2)
        if t_apex + half > DURATION_S:
            break
        apexes.append({"time_s": t_apex, "height_px": h})
        h_next = HEIGHT_1_PX * RATIO ** (k + 1)
        t_apex += half + math.sqrt(2 * h_next / G_PX_S2)
        k += 1
    return apexes


def centre_at(t):
    """Ball centre (x, y) in image pixels at time t."""
    t_apex, k = FIRST_APEX_S, 0
    while True:
        h = HEIGHT_1_PX * RATIO ** k
        half = math.sqrt(2 * h / G_PX_S2)
        if t <= t_apex + half or k > 60:
            dt = t - t_apex
            return X0_PX + VX_PX_S * t, GROUND_CENTER_Y - (h - 0.5 * G_PX_S2 * dt * dt)
        h_next = HEIGHT_1_PX * RATIO ** (k + 1)
        t_apex += half + math.sqrt(2 * h_next / G_PX_S2)
        k += 1


def render(path):
    from fractions import Fraction

    import av
    import cv2
    import numpy as np

    container = av.open(path, mode="w", format="mp4")
    stream = container.add_stream("mpeg4", rate=FPS)
    stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
    stream.bit_rate = 6_000_000
    floor_y = int(GROUND_CENTER_Y + RADIUS_PX + 1)
    shift = 4
    for i in range(int(round(DURATION_S * FPS))):
        img = np.full((HEIGHT, WIDTH, 3), BACKGROUND_BGR, dtype=np.uint8)
        cv2.rectangle(img, (0, floor_y), (WIDTH - 1, HEIGHT - 1), FLOOR_BGR, -1)
        cv2.putText(img, "SIMULATED", (WIDTH - 130, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (90, 90, 90), 1, cv2.LINE_AA)
        x, y = centre_at(i / FPS)
        cv2.circle(img, (int(round(x * 2 ** shift)), int(round(y * 2 ** shift))), RADIUS_PX * 2 ** shift, BALL_BGR, -1,
                   cv2.LINE_AA, shift)
        frame = av.VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts, frame.time_base = i, Fraction(1, FPS)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


if __name__ == "__main__":
    import sys

    out = "/tmp/SIMULATED-bouncing-ball.mp4"
    render(out)
    with open(out, "rb") as fh:
        sys.stdout.buffer.write(fh.read())
