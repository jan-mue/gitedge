import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.index:app", reload=True)
