import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageChops, ImageDraw
import pytest

ROOT = Path(__file__).parents[2] / 'technical_library/window_atlas'
spec = importlib.util.spec_from_file_location('window_atlas', ROOT / 'atlas.py')
atlas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)


def config():
    return json.loads((ROOT / 'new_building_v8.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('position', range(12))
def test_drawing_profile_is_independent_of_object_id(position):
    data = config()
    item = SimpleNamespace(**data['WINDOWS'][position])
    original = Image.new('RGB', (440, 220), data['BG'])
    renamed = original.copy()
    atlas.draw_window(ImageDraw.Draw(original), 10, 200, item, data['FRAME'], data['GLASS'])
    alternate = copy.copy(item)
    alternate.id = 999
    atlas.draw_window(ImageDraw.Draw(renamed), 10, 200, alternate, data['FRAME'], data['GLASS'])
    assert ImageChops.difference(original, renamed).getbbox() is None


def test_rejects_missing_source_mapping():
    data = config()
    del data['DOCX_IMAGES']['17']
    with pytest.raises(ValueError, match='explicit source-image mapping'):
        atlas.validate_config(data)


def test_rejects_duplicate_id():
    data = config()
    data['WINDOWS'][1]['id'] = data['WINDOWS'][0]['id']
    with pytest.raises(ValueError, match='Duplicate window ID'):
        atlas.validate_config(data)


def test_rejects_door_leaf_outside_window():
    data = config()
    data['WINDOWS'][0]['door_leaves'] = [5]
    with pytest.raises(ValueError, match='Door leaf outside'):
        atlas.validate_config(data)
