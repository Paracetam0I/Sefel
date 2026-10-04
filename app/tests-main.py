from fastapi import FastAPI

app = FastAPI(
    title="Mi primera app",
    description="Probando fastapi",
    version="0.0.1"
)

@app.get("/")
async def root():
    return {"message":"Hola, no soy una api"}

@app.get("/pc")
async def miPc():
    return {"componentes":"grafica, cpu, ram"}

# GET para leer
@app.get("/items/{item_id}", description="Esta función lee por los items")
async def readitem(item_id: int):
    return {"Item id": item_id, "Tu valor de tipo es": item_id}

# POST para crear
@app.post("/items/")
async def crearitem(name: str):
    return {"Item": name, "created": True}

# PUT para actualizar todo un elemento
@app.put("/items/{item_id}")
async def actualizaritem(item_id: int, name: str):
    return {"item_id": item_id, "name": name}

# DELETE para eliminar un elemento
@app.delete("/items/{item_id}")
async def eliminaritem(item_id: int):
    return {"item_id": item_id, "deleted": True}
