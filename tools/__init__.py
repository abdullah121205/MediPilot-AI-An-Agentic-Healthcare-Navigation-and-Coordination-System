"""Tool registry. To add a tool: subclass Tool in a new file, then add it to build_tools()."""


class Tool:
    name = "tool"
    description = ""
    args_doc = "{}"

    def execute(self, **kwargs):
        raise NotImplementedError


def build_tools():
    from tools.calculator import Calculator
    from tools.data_query import ListFiles, ReadFile, SqlQuery
    from tools.web_search import WebSearch
    tools = [ListFiles(), ReadFile(), SqlQuery(), Calculator(), WebSearch()]
    try:  # healthcare tools (Member 3); never let them break the agent if something is missing
        from tools.agent_tools import healthcare_tools
        tools += healthcare_tools()
    except Exception as e:
        import sys
        print(f"[tools] healthcare tools not loaded: {e}", file=sys.stderr)
    return {t.name: t for t in tools}


def get_tools():
    """Return the tool dictionary {name: Tool instance}."""
    return build_tools()