"""
Textual-based TUI fallback for environments without TTY.
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static
from textual.containers import Container, Vertical
from textual import events

from .state import AppState, Message
from .theme import Theme


class MDPilotTUI(App):
    """MDPilot TUI using Textual."""
    
    CSS = """
    Screen {
        background: #0f172a;
    }
    
    #welcome {
        height: 8;
        border: solid #4682dc;
        padding: 1;
        background: #1e293b;
    }
    
    #messages {
        height: 1fr;
        border: solid #475569;
        padding: 1;
        background: #1e293b;
    }
    
    Input {
        border: solid #60a5fa;
        background: #1e293b;
    }
    """
    
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("tab", "toggle_welcome", "Toggle Welcome"),
    ]
    
    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.show_welcome = True
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        if self.show_welcome:
            yield Static(
                f"MDPilot TUI\nModel: {self.state.model_name}\n\nPress Tab to toggle",
                id="welcome"
            )
        
        yield Static("(No messages yet)", id="messages")
        yield Input(placeholder="Type your message...")
        yield Footer()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        content = event.value.strip()
        if not content:
            return
        
        # Add message
        msg = Message(role="user", content=content)
        self.state.messages.append(msg)
        
        # Update messages display
        messages_widget = self.query_one("#messages", Static)
        lines = []
        for m in self.state.messages:
            role = "User" if m.role == "user" else "Assistant"
            lines.append(f"{role}: {m.content}")
        messages_widget.update("\n\n".join(lines))
        
        # Clear input
        event.input.value = ""
    
    def action_toggle_welcome(self) -> None:
        """Toggle welcome panel."""
        self.show_welcome = not self.show_welcome
        self.refresh(layout=True)


async def main_textual():
    """Run Textual TUI."""
    app = MDPilotTUI()
    await app.run_async()
