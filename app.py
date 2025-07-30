from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from config import UPLOAD_FOLDER
from routes.main import router

app = FastAPI()
app.state.templates = Jinja2Templates(directory="templates")  # Store templates in app.state
app.config = {"UPLOAD_FOLDER": UPLOAD_FOLDER}
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)