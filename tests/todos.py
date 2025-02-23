"""
A simple Todo list api for testing against

TODO: Add authentication and work that out

"""

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(
    title="Todo API",
    description="A simple API for managing a todo list",
    version="1.0.0",
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Local server",
        },
    ],
)


todo_list: list["Todo"] = []


class Todo(BaseModel):
    id: int = Field(default_factory=lambda: len(todo_list))
    title: str
    completed: bool
    tags: list[str] = Field(default_factory=list)


todo_list.append(Todo(title="Buy groceries", completed=True, tags=["shopping"]))
todo_list.append(Todo(title="Walk the dog", completed=False))


@app.get(
    "/todos/all",
    response_model=list[Todo],
    summary="Get all todos",
    description="Get all todos, including completed ones",
    tags=["todos"],
)
async def get_all_todos() -> list[Todo]:
    return todo_list


@app.post(
    "/todos",
    response_model=Todo,
    summary="Create a todo",
    description="Add an item to the todo list",
    tags=["todos"],
)
async def create_todo(todo: Todo):
    todo_list.append(todo)
    return todo


@app.get(
    "/todos/completed",
    response_model=list[Todo],
    summary="Get all completed todos",
    description="Get all todos that are completed",
    tags=["todos"],
)
async def get_completed_todos() -> list[Todo]:
    return [todo for todo in todo_list if todo.completed]


@app.get(
    "/todos/tags/{tag}",
    response_model=list[Todo],
    summary="Get all todos with a given tag",
    description="Get all todos that have the given tag",
    tags=["todos"],
)
async def get_todos_with_tag(tag: str) -> list[Todo]:
    return [todo for todo in todo_list if tag in todo.tags]


@app.put(
    "/todos/{todo_id}",
    response_model=Todo,
    summary="Update a todo",
    description="Update a todo with the given id",
    tags=["todos"],
)
async def update_todo(todo_id: int, todo: Todo):
    todo_list[todo_id] = todo
    return todo


@app.delete(
    "/todos/{todo_id}",
    response_model=Todo,
    summary="Delete a todo",
    description="Delete a todo with the given id",
    tags=["todos"],
)
async def delete_todo(todo_id: int):
    todo = todo_list[todo_id]
    del todo_list[todo_id]
    return todo


@app.get(
    "/todos/tags",
    response_model=list[str],
    summary="Get all tags",
    description="Get all tags",
    tags=["todos"],
)
async def get_all_tags() -> list[str]:
    return list(set(tag for todo in todo_list for tag in todo.tags))
