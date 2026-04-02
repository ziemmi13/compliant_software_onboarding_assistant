# Legal Scout Web App (MVP)

This project now includes:

- ADK agent system under `legal_scout/`
- FastAPI backend wrapper under `api/`
- React + Vite frontend under `frontend/`

## Prerequisites

- Python virtual environment created in `venv/`
- Node.js and npm installed
- Gemini API key configured

## Gemini Configuration

Create `legal_scout/.env` with:

```dotenv
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=your_api_key_here
```

Then load those variables in the shell before starting backend:

```powershell
Get-Content legal_scout/.env | ForEach-Object {
	if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
	$parts = $_ -split '=', 2
	if ($parts.Length -eq 2) {
		[Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), 'Process')
	}
}
```

## Backend

Start backend server:

```powershell
c:/Users/Hyperbook/Desktop/legal-tech/post_hackaton_app/venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000
```

Backend endpoints:

- `GET /health`
- `POST /api/analyze`

## Frontend

From `frontend/`:

```powershell
npm install
npm run dev
```

Open the app at `http://127.0.0.1:5173` (or the URL printed by Vite).

Optional environment variable:

- `VITE_API_BASE_URL` (default: `http://127.0.0.1:8000`)

## First API test

```powershell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/api/analyze" -ContentType "application/json" -Body '{"url":"https://openai.com"}'
```

Note: Some domains can block automated fetches of terms pages; in those cases the API returns blocked links and lower-confidence output instead of clause highlights.

## Backend Tests

```powershell
c:/Users/Hyperbook/Desktop/legal-tech/post_hackaton_app/venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
```
