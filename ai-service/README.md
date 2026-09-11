# HomeWatt Advisor AI Service

Python FastAPI service and deterministic MCP server for Sri Lankan domestic electricity planning.

The MCP layer currently provides tariff resources, appliance priority rules, bill tools, budget planning tools, and grounded prompt templates. LangGraph agents and OpenAI calls are intentionally not implemented yet.

## Install

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run FastAPI

```powershell
uvicorn app.main:app --reload --port 8000
```

## Internal Service Token

The Node.js backend and Python AI service should use the same shared token so only the backend can call Python `/chat`.

Node.js `.env`:

```env
AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_INTERNAL_TOKEN=your_shared_secret_here
```

Python `ai-service/.env`:

```env
AI_SERVICE_INTERNAL_TOKEN=your_shared_secret_here
```

When `AI_SERVICE_INTERNAL_TOKEN` is configured in Python, `/chat` requires:

```http
Authorization: Bearer your_shared_secret_here
```

For local development only, if Python `AI_SERVICE_INTERNAL_TOKEN` is empty, `/chat` allows requests without the header.

Postman example:

```http
POST http://localhost:8000/chat
Content-Type: application/json
Authorization: Bearer your_shared_secret_here
```

```json
{
  "user_id": 1,
  "session_id": 1,
  "message": "My budget is Rs. 3000 for May 2026. I have TV 100W, iron 1000W and water motor 750W."
}
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
