import os
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column
from sqlalchemy.types import LargeBinary
from sqlmodel import Field, Session, SQLModel, create_engine, select

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stories.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

app = FastAPI(title="Story API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Story(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    text: str
    image_data: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    image_filename: str
    image_content_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StoryCreateResponse(SQLModel):
    id: int


class StoryIdResponse(SQLModel):
    id: int


class StoryDetailResponse(SQLModel):
    id: int
    text: str
    created_at: datetime
    image_content_type: str
    image_base64: str


def get_session():
    with Session(engine) as session:
        yield session


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


def validate_image(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {file.content_type}",
        )


@app.post("/stories", response_model=StoryCreateResponse)
async def upload_story(
    text: str = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    validate_image(image)

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload")

    story = Story(
        text=text,
        image_data=image_bytes,
        image_filename=image.filename or "upload",
        image_content_type=image.content_type or "application/octet-stream",
    )

    session.add(story)
    session.commit()
    session.refresh(story)

    return StoryCreateResponse(id=story.id)


@app.get("/stories", response_model=List[StoryIdResponse])
def get_all_stories(session: Session = Depends(get_session)):
    stories = session.exec(select(Story.id).order_by(Story.created_at.desc())).all()
    return [StoryIdResponse(id=story_id) for story_id in stories]


@app.get("/stories/{story_id}", response_model=StoryDetailResponse)
def get_story(story_id: int, session: Session = Depends(get_session)):
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    import base64

    image_base64 = base64.b64encode(story.image_data).decode("utf-8")

    return StoryDetailResponse(
        id=story.id,
        text=story.text,
        created_at=story.created_at,
        image_content_type=story.image_content_type,
        image_base64=image_base64,
    )
