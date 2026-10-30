def load_member3_tools():
    tools = {}
    try:
        # Check if Member 3's app/tools folder exists
        import importlib
        app_tools = importlib.import_module("app.tools")
        # Load functions/classes dynamically
    except ImportError:
        # Fallback to existing tools/ directory
        from tools import build_tools
        tools = build_tools()
    return tools