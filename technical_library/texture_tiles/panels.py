import numpy as np

def kpp_panels(yellow):
    N = 4096
    panels = np.empty((N, N, 3), dtype=np.uint8)
    x = np.arange(N, dtype=np.float32)[None, :]
    rng = np.random.default_rng(2030)
    seams = np.array([0, 1365, 2731, 4096])
    dx = np.min(np.abs(x[:, :, None] - seams[None, None, :]), axis=2)
    col = np.searchsorted(seams[1:-1], x, side='right')
    tints = np.array([[0, 1, -1], [1, -1, 0], [-1, 0, 1], [0, -1, 0], [1, 0, -1], [0, 1, 0], [-1, 0, 1], [0, -1, 1]])
    for top in range(0, N, 128):
        y = np.arange(top, top + 128, dtype=np.float32)[:, None]
        dy = np.minimum(y % 512, 512 - y % 512)
        noise = rng.normal(0, 0.45, (128, N))
        tone = noise + tints[y.astype(int) // 512, col]
        rgb = np.array(yellow, dtype=float)[None, None, :] + tone[:, :, None]
        joint = np.array(yellow, dtype=float) * 0.73
        rgb = np.where(((dx < 2.5) | (dy < 2.5))[:, :, None], joint, rgb)
        panels[top:top + 128] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    panels[-1] = panels[0]
    panels[:, -1] = panels[:, 0]
    return panels
