from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from .database import get_session
from .models import Recipe

router = APIRouter()


class Ingredient(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None


class RecipeSaveRequest(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    ingredients: List[Ingredient] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class RecipeResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    instructions: Optional[str]
    ingredients: List[Ingredient]
    tags: List[str]

    @classmethod
    def from_model(cls, recipe: Recipe) -> "RecipeResponse":
        ingredients = [Ingredient(**item) for item in recipe.ingredients_json or []]
        return cls(
            id=recipe.id,
            name=recipe.name,
            description=recipe.description,
            instructions=recipe.instructions,
            ingredients=ingredients,
            tags=recipe.tags or [],
        )


@router.post("/recipes.save", response_model=RecipeResponse)
def recipes_save(payload: RecipeSaveRequest, session: Session = Depends(get_session)):
    now = datetime.now(timezone.utc)
    if payload.id:
        recipe = session.get(Recipe, payload.id)
    else:
        recipe = None
    if recipe:
        recipe.name = payload.name
        recipe.description = payload.description
        recipe.instructions = payload.instructions
        recipe.ingredients_json = [item.model_dump() for item in payload.ingredients]
        recipe.tags = payload.tags
        recipe.updated_at = now
    else:
        recipe = Recipe(
            name=payload.name,
            description=payload.description,
            instructions=payload.instructions,
            ingredients_json=[item.model_dump() for item in payload.ingredients],
            tags=payload.tags,
            created_at=now,
            updated_at=now,
        )
        session.add(recipe)
    recipe.updated_at = now
    session.commit()
    session.refresh(recipe)
    return RecipeResponse.from_model(recipe)


@router.get("/recipes.get", response_model=RecipeResponse)
def recipes_get(id: str, session: Session = Depends(get_session)):
    recipe = session.get(Recipe, id)
    if not recipe:
        raise HTTPException(404, "Recipe not found")
    return RecipeResponse.from_model(recipe)


@router.get("/recipes.list", response_model=List[RecipeResponse])
def recipes_list(search: Optional[str] = Query(None), session: Session = Depends(get_session)):
    query = select(Recipe)
    if search:
        pattern = f"%{search.lower()}%"
        query = query.where(func.lower(Recipe.name).like(pattern))
    query = query.order_by(Recipe.created_at.desc())
    recipes = session.exec(query).all()
    return [RecipeResponse.from_model(r) for r in recipes]


class RecipeDeleteRequest(BaseModel):
    id: str


@router.post("/recipes.delete")
def recipes_delete(payload: RecipeDeleteRequest, session: Session = Depends(get_session)):
    recipe = session.get(Recipe, payload.id)
    if not recipe:
        raise HTTPException(404, "Recipe not found")
    session.delete(recipe)
    session.commit()
    return {"status": "deleted"}
