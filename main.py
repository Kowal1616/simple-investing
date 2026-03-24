from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "FastAPI engine is running",
        "project": "SimpleInvesting"
    }
