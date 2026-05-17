# FastAPI - Request Body

## Overview

When you need to send data from a client to your API, you send it as a request body.
A request body is data sent by the client to your API.
A response body is the data your API sends to the client.

FastAPI uses Pydantic models to declare request bodies.

## Declare a Request Body

First, import `BaseModel` from Pydantic:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

app = FastAPI()

@app.post("/items/")
async def create_item(item: Item):
    return item
```

## Using the Model

Inside the function, you can access all the attributes of the model directly:

```python
@app.post("/items/")
async def create_item(item: Item):
    item_dict = item.dict()
    if item.tax:
        price_with_tax = item.price + item.tax
        item_dict.update({"price_with_tax": price_with_tax})
    return item_dict
```

## Request Body + Path Parameters

You can declare both path parameters and a request body at the same time:

```python
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    return {"item_id": item_id, **item.dict()}
```

## Request Body + Path + Query Parameters

You can also mix all three together:

```python
@app.put("/items/{item_id}")
async def update_item(
    item_id: int,
    item: Item,
    q: Optional[str] = None
):
    result = {"item_id": item_id, **item.dict()}
    if q:
        result.update({"q": q})
    return result
```

FastAPI recognizes each parameter by:
- **Path parameter**: declared in the path string
- **Query parameter**: singular type (int, str, etc.) not in path
- **Request body**: Pydantic model type

## Nested Models

Pydantic models can be nested:

```python
class Image(BaseModel):
    url: str
    name: str

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None
    image: Optional[Image] = None

@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    results = {"item_id": item_id, "item": item}
    return results
```

## Field Validation

Use `Field` from Pydantic to add validation to model fields:

```python
from pydantic import BaseModel, Field

class Item(BaseModel):
    name: str
    description: Optional[str] = Field(None, max_length=300)
    price: float = Field(..., gt=0, description="Price must be greater than zero")
    tax: Optional[float] = None
```
