"""
MDPilot TUI - Main Application.

PyRatatui-based terminal user interface with 30 FPS rendering.
Implements the complete 7-layer layout with real-time LLM streaming.
"""
import asyncio
import sys
from typing import Optional
from datetime import datetime

try:
    from pyratatui import AsyncTerminal, Block, Paragraph, Layout, Constraint, Direction
    from pyratatui import Color, Style, Alignment, BorderType
    from pyratatui import PyKeyEvent as KeyEvent
except ImportError as e:
    print("❌ Error: pyratatui not installed")
    print("Install with: pip install pyratatui")
    print(f"Details: {e}")
    sys.exit(1)

from .state import AppState, Message
from .theme import Theme
from .layout import LayoutManager
from .communication.websocket_client import WebSocketClient


class MDPilotTUI:
    """
    Main TUI application.

    Features:
    - 30 FPS rendering loop
    - 7-layer vertical layout
    - Real-time LLM streaming
    - WebSocket communication
    - Responsive design
    """

    def __init__(self, websocket_url: str = "ws://localhost:8000/ws"):
        """
        Initialize TUI application.

        Args:
            websocket_url: Backend WebSocket endpoint
        """
        self.state = AppState()
        self.theme = Theme()
        self.layout_manager = LayoutManager()
        self.websocket_url = websocket_url
        self.ws_client: Optional[WebSocketClient] = None
        self.running = True

        # Animation state
        self.cursor_visible = True
        self.cursor_blink_counter = 0
        self.spinner_index = 0
        self.spinner_chars = ["✳", "✴", "✵", "✶"]

    async def run(self) -> None:
        """Main application entry point."""
        # Try to connect WebSocket (optional for Phase 1)
        try:
            self.ws_client = WebSocketClient(self.websocket_url)
            connected = await self.ws_client.connect()
            self.state.connected = connected
        except Exception as e:
            # WebSocket connection failed - continue in offline mode
            self.state.connected = False

        # Start AsyncTerminal
        async with AsyncTerminal() as term:
            term.hide_cursor()

            # Get initial terminal size from first frame
            initial_size_set = False

            # 30 FPS event loop
            async for event in term.events(fps=30):
                # Handle events
                if event:
                    handled = await self.handle_event(event)
                    if not handled and not self.running:
                        break

                # Update animations
                self.update_animations()

                # Render frame
                def draw(frame):
                    nonlocal initial_size_set

                    # Set terminal size from frame on first render
                    if not initial_size_set:
                        area = frame.area
                        self.layout_manager.update_terminal_size(area.width, area.height)
                        initial_size_set = True

                    self.render(frame)

                term.draw(draw)

            term.show_cursor()

        # Cleanup
        if self.ws_client:
            await self.ws_client.close()

    async def handle_event(self, event: KeyEvent) -> bool:
        """
        Handle keyboard events.

        Args:
            event: Keyboard event

        Returns:
            True if event was handled
        """
        if not isinstance(event, KeyEvent):
            return False

        # Ctrl+C or Ctrl+D: Quit
        if (event.code == "c" and event.ctrl) or \
           (event.code == "d" and event.ctrl):
            self.running = False
            return True

        # q: Quit (when idle)
        if event.code == "q" and not self.state.streaming.is_streaming:
            self.running = False
            return True

        # Tab: Toggle welcome panel
        if event.code == "tab":
            self.layout_manager.toggle_welcome_panel()
            return True

        # Enter: Send message
        if event.code == "enter":
            await self.send_message()
            return True

        # Backspace: Delete character
        if event.code == "backspace":
            if self.state.ui.input_buffer:
                self.state.ui.input_buffer = self.state.ui.input_buffer[:-1]
                self.state.ui.cursor_position = len(self.state.ui.input_buffer)
            return True

        # Printable characters: Add to input buffer
        if len(event.code) == 1 and event.code.isprintable():
            self.state.ui.input_buffer += event.code
            self.state.ui.cursor_position = len(self.state.ui.input_buffer)
            return True

        # Arrow keys: Scroll messages (TODO: implement in Phase 2)
        if event.code in ["up", "down"]:
            return True

        return False

    async def send_message(self) -> None:
        """Send current input buffer as message."""
        content = self.state.ui.input_buffer.strip()
        if not content:
            return

        # Create user message
        msg = Message(role="user", content=content)
        self.state.messages.append(msg)

        # Clear input
        self.state.ui.input_buffer = ""
        self.state.ui.cursor_position = 0

        # Hide welcome panel after first message
        if len(self.state.messages) == 1:
            self.layout_manager.welcome_panel_visible = False

        # TODO: Send to WebSocket in Phase 3
        # For now, add a mock assistant response
        mock_response = Message(
            role="assistant",
            content=f"收到消息: {content}\n\n(这是模拟响应，WebSocket 通信将在 Phase 3 实现)"
        )
        self.state.messages.append(mock_response)

    def update_animations(self) -> None:
        """Update animation states (cursor blink, spinner)."""
        # Cursor blink (1 Hz = 30 frames per blink)
        self.cursor_blink_counter += 1
        if self.cursor_blink_counter >= 15:  # 0.5 seconds at 30 FPS
            self.cursor_visible = not self.cursor_visible
            self.cursor_blink_counter = 0

        # Spinner rotation (4 frames per rotation)
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)

    def render(self, frame) -> None:
        """
        Render all UI components.

        Args:
            frame: PyRatatui Frame object
        """
        area = frame.area

        # Calculate layout
        layout_spec = self.layout_manager.calculate_layout()

        # Create vertical layout
        constraints = []
        for layer_name, height in layout_spec:
            constraints.append(Constraint.Length(height))

        chunks = Layout.default() \
            .direction(Direction.Vertical) \
            .constraints(constraints) \
            .split(area)

        # Render each layer
        chunk_index = 0
        for layer_name, _ in layout_spec:
            if layer_name == "title_bar":
                self.render_title_bar(frame, chunks[chunk_index])
            elif layer_name == "welcome_panel":
                self.render_welcome_panel(frame, chunks[chunk_index])
            elif layer_name == "status_row":
                self.render_status_row(frame, chunks[chunk_index])
            elif layer_name == "bottom_status":
                self.render_bottom_status(frame, chunks[chunk_index])
            elif layer_name == "input_area":
                self.render_input_area(frame, chunks[chunk_index])
            elif layer_name == "footer":
                self.render_footer(frame, chunks[chunk_index])
            elif layer_name == "messages_area":
                self.render_messages_area(frame, chunks[chunk_index])

            chunk_index += 1

    def render_title_bar(self, frame, area) -> None:
        """Render title bar."""
        text = "─ MDPilot v1.0 ─"
        para = Paragraph(text) \
            .style(Style().fg(Color.rgb(*self.theme.primary))) \
            .alignment(Alignment.Center)
        frame.render_widget(para, area)

    def render_welcome_panel(self, frame, area) -> None:
        """Render welcome panel (placeholder for Phase 2)."""
        block = Block() \
            .title("Welcome") \
            .bordered() \
            .border_style(Style().fg(Color.rgb(*self.theme.primary)))

        text = f"🐙 MDPilot TUI\n\nModel: {self.state.model_name}\n\nPress Tab to toggle"
        para = Paragraph(text) \
            .block(block) \
            .alignment(Alignment.Center)

        frame.render_widget(para, area)

    def render_messages_area(self, frame, area) -> None:
        """Render messages area."""
        block = Block() \
            .title("Messages") \
            .bordered() \
            .border_style(Style().fg(Color.rgb(*self.theme.border)))

        # Format messages
        lines = []
        for msg in self.state.messages:
            role = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role}:")
            lines.append(msg.content)
            lines.append("")  # Empty line

        # Add streaming cursor if active
        if self.state.streaming.is_streaming and self.cursor_visible:
            if lines:
                lines[-1] += "▊"

        text = "\n".join(lines) if lines else "(No messages yet)\n\nType a message and press Enter to start"

        para = Paragraph(text).block(block)
        frame.render_widget(para, area)

    def render_status_row(self, frame, area) -> None:
        """Render status row (for LLM streaming)."""
        spinner = self.spinner_chars[self.spinner_index]
        text = f"{spinner} Calling tool (claude-opus-4-7)..."

        para = Paragraph(text) \
            .style(Style().fg(Color.rgb(*self.theme.info)))

        frame.render_widget(para, area)

    def render_bottom_status(self, frame, area) -> None:
        """Render bottom status bar."""
        # Left: Task badge + model + tool
        badge = "[IDLE]"
        left_text = f"{badge} {self.state.model_name}"

        # Right: Shortcuts
        right_text = "Tab 折叠 · q 退出 · Ctrl+C 中断"

        # Combine (TODO: proper left/right alignment in Phase 2)
        text = f"{left_text}    {right_text}"

        para = Paragraph(text) \
            .style(Style.default().fg(Color.rgb(*self.theme.text_dim)))

        frame.render_widget(para, area)

    def render_input_area(self, frame, area) -> None:
        """Render input area."""
        block = Block() \
            .title("Input") \
            .bordered() \
            .border_style(Style().fg(Color.rgb(*self.theme.border_focus)))

        # Show prompt and input buffer
        cursor = "▊" if self.cursor_visible else " "
        text = f"› {self.state.ui.input_buffer}{cursor}"

        para = Paragraph(text).block(block)
        frame.render_widget(para, area)

    def render_footer(self, frame, area) -> None:
        """Render footer."""
        # Left: Shortcuts
        left_text = "Enter send · Ctrl+C interrupt"

        # Right: Stats
        status = "🟢 Connected" if self.state.connected else "🔴 Disconnected"
        tokens = self.state.tokens_used
        tokens_str = f"{tokens / 1000:.1f}K" if tokens >= 1000 else str(tokens)
        right_text = f"{status} · {tokens_str} tokens"

        # Combine (TODO: proper left/right alignment in Phase 2)
        text = f"{left_text}    {right_text}"

        para = Paragraph(text) \
            .style(Style().fg(Color.rgb(*self.theme.text_dim)))

        frame.render_widget(para, area)


async def main(websocket_url: str = "ws://localhost:8000/ws") -> None:
    """
    Main entry point for TUI.

    Args:
        websocket_url: Backend WebSocket endpoint
    """
    app = MDPilotTUI(websocket_url)
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
