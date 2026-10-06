"""Periodic metre-space facade color pattern; numpy, no DCC dependency."""
import numpy as np

def pattern(mid, x, y, color, panel_joint=.005, panel_dimensions=None):
    """Sample RGB at broadcastable NumPy x/y arrays in metres.

    ID 101 uses brick; IDs 102-105 use solid panels. Dimensions are (width,
    height); omitted dimensions retain the historical v003/v004 sizes.
    For v005 pass (1.2, .6) for brick or (.6, 1.2) for the other panels.
    Color is a normalized RGB triplet; panel_joint is the full joint width.
    """
    pw, ph = panel_dimensions or ((1.6, 1.2) if mid == 101 else (1.2, 1.6))
    px, py = x % pw, y % ph
    color = np.asarray(color)
    shape = np.broadcast_shapes(x.shape, y.shape)
    if mid == 101:
        row = np.floor(py / .075)
        col = np.floor((px + (row % 2) * .13) / .26)
        mortar = ((py % .075) < .01) | (((px + (row % 2) * .13) % .26) < .01)
        variation = .92 + .12 * (.5 + .5 * np.sin(col * 12.31 + row * 43.11))
        # Wrapped coordinates make fine variation periodic as well as the joints.
        texture = .985 + .015 * np.sin(px * 370 + np.sin(py * 211)) * np.sin(py * 470)
        rgb = np.broadcast_to(color, (*shape, 3)) * variation[..., None] * texture[..., None]
        rgb = np.where(mortar[..., None], np.array([.29, .265, .23]), rgb)
        joint = (np.minimum(px, pw-px) < panel_joint/2) | (np.minimum(py, ph-py) < panel_joint/2)
        joint_color = np.array([.025, .023, .020])
    else:
        rgb = np.broadcast_to(color, (*shape, 3)).copy()
        joint = (np.minimum(px, pw-px) < panel_joint/2) | (np.minimum(py, ph-py) < panel_joint/2)
        joint_color = color * .4
    return np.clip(np.where(joint[..., None], joint_color, rgb), 0, 1)

def raster(mid, width, height, extent, color, joint=.005, offset=(0,0), panel_dimensions=None):
    """Bottom-origin float32 RGB (height, width, 3), with 4x4 subpixel samples.

    extent and offset are (x, y) in metres; width/height are pixel counts.
    Panel dimensions follow pattern(), including its historical defaults.
    """
    result = np.empty((height, width, 3), dtype=np.float32)
    for start in range(0, height, 64):
        end = min(start+64, height)
        rgb = np.zeros((end-start, width, 3), dtype=np.float32)
        for dx in (.125, .375, .625, .875):
            for dy in (.125, .375, .625, .875):
                x = (np.arange(width)[None, :] + dx) * extent[0]/width + offset[0]
                y = (np.arange(start,end)[:, None] + dy) * extent[1]/height + offset[1]
                rgb += pattern(mid,x,y,color,joint,panel_dimensions)/16
        result[start:end] = rgb
    return result
