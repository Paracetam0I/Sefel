from fastapi import FastAPI

app = FastAPI(
    title="Mi primera app",
    description="Probando fastapi",
    version="0.0.1"
)

@app.get("/")
async def root():
    return {"message":"Hola, no soy una api"}

@app.get("/item/{item_id}")
async def readitem(item_id: int):
    return {"Item id": item_id, "Tu valor de tipo es": item_id}
