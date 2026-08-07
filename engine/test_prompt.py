import json

tool_result = {
    "success": True, 
    "tool": "get_critical_path",
    "total_count": 861, 
    "displayed_count": 20,
    "is_truncated": True, 
    "data": [{"id": i, "code": f"A{i}", "name": f"Task {i}", "float_days": 0.0, "delay_days": 0} for i in range(20)], 
    "all_items": [{"id": i, "code": f"A{i}", "name": f"Task {i}", "float_days": 0.0, "delay_days": 0} for i in range(861)], 
}
optim_tool_result = tool_result.copy()
full_data = tool_result.get("all_items", tool_result.get("data", []))
total_count = tool_result.get("total_count", len(full_data))

limit = 20
is_truncated = total_count > limit

if is_truncated:
    optim_tool_result["data"] = full_data[:limit]

user_msg = (
    f'Query: "Critical path tasks"\n'
    f'Tool Executed: {tool_result["tool"]}\n'
    f'BACKEND DATA (showing {len(optim_tool_result["data"])} of {total_count} items):\n'
    f'{json.dumps(optim_tool_result["data"], default=str)}'
)
print(user_msg)
