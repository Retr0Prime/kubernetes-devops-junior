from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from app.models import TodoCreate, TodoResponse
from app.database import get_db, create_tables, TodoModel

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield

app = FastAPI(title="Todo API - Kubernetes", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)

@app.get("/")
def root():
    return {"message": "Todo API en Kubernetes"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/todos", response_model=TodoResponse)
def create_todo(todo: TodoCreate, db: Session = Depends(get_db)):
    item = TodoModel(title=todo.title, description=todo.description or "")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.get("/todos", response_model=list[TodoResponse])
def list_todos(db: Session = Depends(get_db)):
    return db.query(TodoModel).all()

@app.get("/todos/{todo_id}", response_model=TodoResponse)
def get_todo(todo_id: int, db: Session = Depends(get_db)):
    item = db.query(TodoModel).filter(TodoModel.id == todo_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return item

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    item = db.query(TodoModel).filter(TodoModel.id == todo_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    db.delete(item)
    db.commit()
    return {"message": "Tarea eliminada"}
