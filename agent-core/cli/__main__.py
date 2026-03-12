"""Allow running the CLI as a module: python -m cli"""
try:
    from .sales_agent_cli import cli
except ImportError:
    import sys
    from pathlib import Path
    _parent = str(Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from cli.sales_agent_cli import cli

if __name__ == "__main__":
    cli()
