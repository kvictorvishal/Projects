# FastAPI - Query Parameters

## Overview

When you declare function parameters that are not part of the path parameters, FastAPI automatically interprets them as query parameters.

## Basic Query Parameters

```python
from fastapi import FastAPI

app = FastAPI()

fake_items_db = [{"item_name": "Foo"}, {"item_name": "Bar"}, {"item_name": "Baz"}]

@app.get("/items/")
async def read_item(skip: int = 0, limit: int = 10):
    return fake_items_db[skip : skip + limit]
```

The query string is the set of key-value pairs after the `?` in a URL, separated by `&` characters.
For the URL `/items/?skip=0&limit=10`, the query parameters are `skip=0` and `limit=10`.

## Optional Query Parameters

Optional parameters can be declared by setting their default to `None`:

```python
from typing import Optional
from fastapi import FastAPI

app = FastAPI()

@app.get("/items/{item_id}")
async def read_item(item_id: str, q: Optional[str] = None):
    if q:
        return {"item_id": item_id, "q": q}
    return {"item_id": item_id}
```

## Required Query Parameters

If you don't declare a default value, the parameter is required:

```python
@app.get("/items/{item_id}")
async def read_item(item_id: str, needy: str):
    return {"item_id": item_id, "needy": needy}
```

## Boolean Query Parameters

FastAPI can parse boolean query parameters from strings like `true`, `1`, `on`, `yes`:

```python
@app.get("/items/{item_id}")
async def read_item(item_id: str, short: bool = False):
    item = {"item_id": item_id}
    if not short:
        item.update({"description": "This is an amazing item"})
    return item
```

## Multiple Query Parameters

You can mix path and query parameters freely:

```python
@app.get("/users/{user_id}/items/{item_id}")
async def read_user_item(
    user_id: int,
    item_id: str,
    q: Optional[str] = None,
    short: bool = False
):
    item = {"item_id": item_id, "owner_id": user_id}
    if q:
        item.update({"q": q})
    if not short:
        item.update({"description": "This is an amazing item"})
    return item
```

## Query Parameter Validation

Use `Query` from FastAPI to add validation rules:

```python
from fastapi import FastAPI, Query

@app.get("/items/")
async def read_items(q: Optional[str] = Query(None, max_length=50, min_length=3)):
    results = {"items": [{"item_id": "Foo"}, {"item_id": "Bar"}]}
    if q:
        results.update({"q": q})
    return results
```
