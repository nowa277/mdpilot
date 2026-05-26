"""Tests for MDPilot TUI application"""
import pytest
from pathlib import Path
from textual.pilot import Pilot


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file for testing"""
    config_file = tmp_path / "tui_config.yaml"
    config_content = """
api_endpoint: http://localhost:8000
theme: dark
layout:
  show_header: true
  show_footer: true
"""
    config_file.write_text(config_content)
    return config_file


class TestMDPilotTUI:
    """Test suite for MDPilot TUI application"""

    def test_app_imports(self):
        """Test that TUI app can be imported"""
        from mdpilot.tui.app import MDPilotTUI
        assert MDPilotTUI is not None

    def test_app_initialization(self):
        """Test that TUI app can be initialized"""
        from mdpilot.tui.app import MDPilotTUI
        app = MDPilotTUI()
        assert app is not None
        assert app.title == "MDPilot"

    def test_app_with_config(self, temp_config_file):
        """Test that TUI app can be initialized with config"""
        from mdpilot.tui.app import MDPilotTUI
        app = MDPilotTUI(config_path=temp_config_file)
        assert app is not None
        assert app.config is not None
        assert app.config.api_endpoint == "http://localhost:8000"
        assert app.config.theme == "dark"

    def test_app_default_config(self):
        """Test that TUI app uses default config when no config file provided"""
        from mdpilot.tui.app import MDPilotTUI
        app = MDPilotTUI()
        assert app.config is not None
        assert app.config.api_endpoint == "http://localhost:8000"
        assert app.config.theme == "dark"

    @pytest.mark.asyncio
    async def test_app_compose(self):
        """Test that TUI app composes widgets correctly"""
        from mdpilot.tui.app import MDPilotTUI
        app = MDPilotTUI()
        async with app.run_test() as pilot:
            # Check that header and footer are present
            assert pilot.app.query("Header")
            assert pilot.app.query("Footer")

    @pytest.mark.asyncio
    async def test_app_key_bindings(self):
        """Test that TUI app has correct key bindings"""
        from mdpilot.tui.app import MDPilotTUI
        app = MDPilotTUI()
        async with app.run_test() as pilot:
            # Check that quit binding exists in BINDINGS class attribute
            assert any(b.key == "q" for b in app.BINDINGS)


class TestTUIConfig:
    """Test suite for TUI configuration"""

    def test_config_imports(self):
        """Test that TUI config can be imported"""
        from mdpilot.tui.config import TUIConfig
        assert TUIConfig is not None

    def test_config_defaults(self):
        """Test that TUI config has correct defaults"""
        from mdpilot.tui.config import TUIConfig
        config = TUIConfig()
        assert config.api_endpoint == "http://localhost:8000"
        assert config.theme == "dark"
        assert config.layout.show_header is True
        assert config.layout.show_footer is True

    def test_config_from_dict(self):
        """Test that TUI config can be created from dict"""
        from mdpilot.tui.config import TUIConfig
        config_dict = {
            "api_endpoint": "http://example.com:9000",
            "theme": "light",
            "layout": {
                "show_header": False,
                "show_footer": True,
            }
        }
        config = TUIConfig(**config_dict)
        assert config.api_endpoint == "http://example.com:9000"
        assert config.theme == "light"
        assert config.layout.show_header is False
        assert config.layout.show_footer is True

    def test_config_load_from_file(self, temp_config_file):
        """Test that TUI config can be loaded from file"""
        from mdpilot.tui.config import TUIConfig
        config = TUIConfig.from_file(temp_config_file)
        assert config.api_endpoint == "http://localhost:8000"
        assert config.theme == "dark"
        assert config.layout.show_header is True
        assert config.layout.show_footer is True

    def test_config_load_from_nonexistent_file(self):
        """Test that TUI config returns defaults for nonexistent file"""
        from mdpilot.tui.config import TUIConfig
        config = TUIConfig.from_file(Path("/nonexistent/config.yaml"))
        assert config.api_endpoint == "http://localhost:8000"
        assert config.theme == "dark"

    def test_config_validation(self):
        """Test that TUI config validates theme values"""
        from mdpilot.tui.config import TUIConfig
        with pytest.raises(ValueError):
            TUIConfig(theme="invalid_theme")
