import json

from driver.instance import seed_plugin_home


def test_seed_copies_index_and_symlinks_each_plugin(tmp_path):
    real = tmp_path / "real-plugins"
    (real / "ui_tester").mkdir(parents=True)
    (real / "designer").mkdir(parents=True)
    (real / "index.json").write_text(json.dumps({
        "format": 1,
        "plugins": [{"plugin_id": "ui_tester"}, {"plugin_id": "designer"}],
    }), encoding="utf-8")

    home = tmp_path / "home"
    seed_plugin_home(home, plugins_root=real)

    dest = home / ".locksmith" / "plugins"
    assert (dest / "index.json").exists()
    assert json.loads((dest / "index.json").read_text())["plugins"][0]["plugin_id"] == "ui_tester"
    assert (dest / "ui_tester").is_symlink()
    assert (dest / "designer").is_symlink()
    assert (dest / "ui_tester").resolve() == (real / "ui_tester").resolve()
    assert (dest / "designer").resolve() == (real / "designer").resolve()


def test_seed_skips_missing_plugin_dirs(tmp_path):
    real = tmp_path / "real-plugins"
    (real / "ui_tester").mkdir(parents=True)
    (real / "index.json").write_text(json.dumps({
        "format": 1,
        "plugins": [{"plugin_id": "ui_tester"}, {"plugin_id": "ghost"}],
    }), encoding="utf-8")

    home = tmp_path / "home"
    seed_plugin_home(home, plugins_root=real)

    dest = home / ".locksmith" / "plugins"
    assert (dest / "ui_tester").is_symlink()
    assert not (dest / "ghost").exists()


def test_seed_is_idempotent(tmp_path):
    real = tmp_path / "real-plugins"
    (real / "ui_tester").mkdir(parents=True)
    (real / "index.json").write_text(json.dumps({
        "format": 1,
        "plugins": [{"plugin_id": "ui_tester"}],
    }), encoding="utf-8")
    home = tmp_path / "home"
    seed_plugin_home(home, plugins_root=real)
    seed_plugin_home(home, plugins_root=real)  # must not raise
    dest = home / ".locksmith" / "plugins"
    assert (dest / "ui_tester").is_symlink()
    assert (dest / "ui_tester").resolve() == (real / "ui_tester").resolve()
