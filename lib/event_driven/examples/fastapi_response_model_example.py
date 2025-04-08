from fastapi import FastAPI, HTTPException
from event_driven.examples.model import User, UserCreate, UserRead, UserUpdate

app = FastAPI()

fake_users_db = {}
user_counter = 0


@app.post("/users/", response_model=UserRead, status_code=201)
async def create_user(user_in: UserCreate): # type: ignore
    """
    Creates a new user.
    """
    global user_counter
    user_counter += 1
    user_id = user_counter

    user_data = user_in.model_dump()
    user_data["user_id"] = user_id

    fake_users_db[user_id] = user_data

    return user_data

@app.get("/users/{user_id}", response_model=UserRead)
async def read_user(user_id: int):
    """
    Gets a user by their ID.
    """
    if user_id not in fake_users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return fake_users_db[user_id]

@app.put("/users/{user_id}", response_model=UserRead)
async def update_user(user_id: int, user_in: UserUpdate): # type: ignore
    """
    Updates a user by their ID.
    """
    global fake_users_db
    if user_id not in fake_users_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update non Null fields
    for field, value in user_in.model_dump().items():
        if value is not None:
            fake_users_db[user_id][field] = value
    return fake_users_db[user_id]

@app.delete("/users/{user_id}", response_model=UserRead)
async def delete_user(user_id: int):
    """
    Deletes a user by their ID.
    """
    global fake_users_db
    if user_id not in fake_users_db:
        raise HTTPException(status_code=404, detail="User not found")
    deleted_user = fake_users_db[user_id]
    del fake_users_db[user_id]
    return deleted_user

@app.get("/")
async def read_root():
    return {"message": "FastAPI Response Model Example"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 