# FastAPI - Path Parameters

## Introduction

FastAPI allows you to declare path parameters with the same syntax used by Python format strings.

## Basic Path Parameters

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

When you declare path parameters with Python type hints, FastAPI automatically:
- Validates the data
- Converts the data to the declared type
- Documents the parameter in the auto-generated API schema

## Path Parameters with Types

You can declare the type of path parameters using standard Python type hints:

```python
@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}
```

If you declare the type as `int` and send a non-integer like `"foo"`, FastAPI will return an error.

## Predefined Values with Enum

If you want the path parameter to have fixed allowed values, use Python Enum:

```python
from enum import Enum
from fastapi import FastAPI

class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"

app = FastAPI()

@app.get("/models/{model_name}")
async def get_model(model_name: ModelName):
    if model_name is ModelName.alexnet:
        return {"model_name": model_name, "message": "Deep Learning FTW!"}
    if model_name.value == "lenet":
        return {"model_name": model_name, "message": "LeCNN all the images"}
    return {"model_name": model_name, "message": "Have some residuals"}
```

## Order Matters

When creating routes, be careful about the order. Fixed paths must be declared before parameterized ones:

```python
@app.get("/users/me")      # This must come first
async def read_user_me():
    return {"user_id": "the current user"}

@app.get("/users/{user_id}")  # This comes second
async def read_user(user_id: str):
    return {"user_id": user_id}
```

## File Paths in Parameters

If you need a path parameter to contain a path (with slashes), declare it as `path`:

```python
@app.get("/files/{file_path:path}")
async def read_file(file_path: str):
    return {"file_path": file_path}
```
