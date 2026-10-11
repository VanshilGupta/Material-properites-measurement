"""settings.ini loading: defaults, parsing, and bad-value fallback."""

import textwrap

import app_config


def _write(tmp_path, body: str):
    path = tmp_path / "settings.ini"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_missing_file_gives_safe_defaults(tmp_path):
    s = app_config._load(tmp_path / "nope.ini")
    assert s == app_config.Settings()
    assert s.remote_mode is False          # local mode, no secrets baked in
    assert s.remote_token == ""
    assert s.eurotherm_auto_detect is True


def test_values_and_inline_comments_are_parsed(tmp_path):
    path = _write(tmp_path, """
        [mode]
        remote = true
        [remote]
        host  = 10.0.0.7
        token = a%b
        [eurotherm]
        com_port = 7      # COM7
        auto_detect = false
        probe_timeout = 0.5
        [sample]
        default_diameter_mm = 12.5
    """)
    s = app_config._load(path)
    assert s.remote_mode is True
    assert s.remote_host == "10.0.0.7"
    assert s.remote_token == "a%b"          # '%' kept literally
    assert s.eurotherm_com_port == 7
    assert s.eurotherm_auto_detect is False
    assert s.eurotherm_probe_timeout == 0.5
    assert s.default_sample_diameter_mm == 12.5


def test_bad_value_falls_back_to_default(tmp_path, capsys):
    path = _write(tmp_path, """
        [eurotherm]
        com_port = five
        [remote]
        port = 9000
    """)
    s = app_config._load(path)
    assert s.eurotherm_com_port == app_config.Settings().eurotherm_com_port
    assert s.remote_port == 9000            # other keys unaffected
    assert "Invalid [eurotherm] com_port" in capsys.readouterr().out
