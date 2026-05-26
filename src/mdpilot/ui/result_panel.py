"""Result display panels using Rich."""

from __future__ import annotations

import json
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


class ResultPanel:
    """Formats and displays task results."""
    
    def __init__(self):
        self.console = Console()
    
    def display_table(self, data: list[dict[str, Any]], title: str) -> None:
        """Display data as a table."""
        if not data:
            self.console.print(f"[yellow]{title}: No data[/yellow]")
            return
        
        table = Table(title=title, show_header=True, header_style="bold magenta")
        
        if data:
            for key in data[0]:
                table.add_column(key, style="cyan")
            
            for row in data:
                table.add_row(*[str(v) for v in row.values()])
        
        self.console.print(table)
    
    def display_json(self, data: dict[str, Any], title: str) -> None:
        """Display JSON with syntax highlighting."""
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        panel = Panel(syntax, title=title, border_style="blue")
        self.console.print(panel)
    
    def display_yaml(self, data: dict[str, Any], title: str) -> None:
        """Display YAML with syntax highlighting."""
        yaml_str = yaml.dump(data, allow_unicode=True, default_flow_style=False)
        syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=True)
        panel = Panel(syntax, title=title, border_style="blue")
        self.console.print(panel)
    
    def display_text(self, text: str, title: str, syntax: str | None = None) -> None:
        """Display text with optional syntax highlighting."""
        if syntax:
            syntax_obj = Syntax(text, syntax, theme="monokai", line_numbers=True)
            panel = Panel(syntax_obj, title=title, border_style="blue")
        else:
            panel = Panel(text, title=title, border_style="blue")
        self.console.print(panel)
    
    def display_success(self, message: str) -> None:
        """Display success message."""
        self.console.print(f"[green]✓ {message}[/green]")
    
    def display_error(self, message: str, error: str | None = None) -> None:
        """Display error message."""
        self.console.print(f"[red]✗ {message}[/red]")
        if error:
            panel = Panel(error, title="Error Details", border_style="red")
            self.console.print(panel)
