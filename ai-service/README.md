# HomeWatt Advisor AI Service

Python FastAPI service and deterministic MCP server for Sri Lankan domestic electricity planning.

The MCP layer currently provides tariff resources, appliance priority rules, bill tools, budget planning tools, and grounded prompt templates. LangGraph agents, OpenAI calls, and MCP client integration are intentionally not implemented yet.

## Install

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run FastAPI

```powershell
uvicorn app.main:app --reload --port 8000
```

## Run MCP Server

The MCP server uses standard input/output transport:

```powershell
python -m mcp_server.server
```

Resources:

- `tariff://sri-lanka/domestic/2026-05`
- `appliances://priority-rules`

Tools:

- `get_billing_days`
- `calculate_appliance_kwh`
- `calculate_domestic_bill`
- `calculate_budget_unit_limit`
- `classify_appliance_priority`
- `generate_initial_usage_plan`

Prompts:

- `create_usage_guide`
- `explain_bill_breakdown`

## Test

Run all deterministic calculation tests:

```powershell
python -m unittest discover -s tests -v
```

Run the May 2026 bill example directly:

```powershell
python -c "from mcp_server.tariff_data import calculate_domestic_bill_data; print(calculate_domestic_bill_data(2026, 5, 105))"
```

For `year=2026`, `month=5`, and `units=105`, the expected final amount is approximately `LKR 2896.41`.
