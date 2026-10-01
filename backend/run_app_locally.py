"""Run the FastAPI application locally with auto-reload."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.index:app", reload=True)
