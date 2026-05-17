# FastAPI - Response Models

## Overview

You can declare the model used for the response by using the `response_model` parameter in path operations like `@app.get()`, `@app.post()`, etc.

## Basic Response Model

```python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None
    tags: list[str] = []

@app.post("/items/", response_model=Item)
async def create_item(item: Item):
    return item
```

## Filtering Response Data

The most important use of `response_model` is to filter output data.
You can have a model with passwords as input, but not include them in the output:

```python
class UserIn(BaseModel):
    username: str
    password: str
    email: str
    full_name: Optional[str] = None

class UserOut(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None

@app.post("/user/", response_model=UserOut)
async def create_user(user: UserIn):
    return user  # password is automatically excluded from response
```

## response_model_exclude_unset

Use `response_model_exclude_unset=True` to only return explicitly set values:

```python
@app.get("/items/{item_id}", response_model=Item, response_model_exclude_unset=True)
async def read_item(item_id: str):
    items = {
        "foo": {"name": "Foo", "price": 50.2},
        "bar": {"name": "Bar", "price": 62, "description": "The bartenders"},
    }
    return items[item_id]
```

## Response Status Codes

You can declare the HTTP status code for the response:

```python
from fastapi import FastAPI, status

@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(name: str):
    return {"name": name}
```

Common status codes:
- `200` - OK (default for GET)
- `201` - Created (use for POST when something is created)
- `204` - No Content
- `404` - Not Found
- `422` - Unprocessable Entity (validation error)

## Returning Errors

Use `HTTPException` to return error responses:

```python
from fastapi import FastAPI, HTTPException

items = {"foo": "The Foo Wrestlers"}

@app.get("/items/{item_id}")
async def read_item(item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item": items[item_id]}
```
