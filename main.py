from fastapi import FastAPI
from routes import router

app = FastAPI()
app.include_router(router)

@app.get("/")
def root():
    return {"message": "Unified Tunisian ID service is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
