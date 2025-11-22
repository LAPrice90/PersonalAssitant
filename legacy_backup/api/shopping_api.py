from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .database import get_session
from .models import PantryItem, PlanWeek, Recipe, ShoppingList

router = APIRouter()


class ShoppingItem(BaseModel):
    name: str
    quantity: float = 0
    unit: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None


class ShoppingGenerateRequest(BaseModel):
    plan_id: Optional[str] = None
    recipe_ids: List[str] = Field(default_factory=list)
    subtract_pantry: bool = True


class ShoppingListResponse(BaseModel):
    list_id: str
    items_by_category: Dict[str, List[ShoppingItem]]


def _gather_ingredients(session: Session, recipe_ids: List[str]) -> List[ShoppingItem]:
    ingredients: List[ShoppingItem] = []
    for recipe_id in recipe_ids:
        recipe = session.get(Recipe, recipe_id)
        if not recipe:
            raise HTTPException(404, f"Recipe {recipe_id} not found")
        for ing in recipe.ingredients_json or []:
            ingredients.append(ShoppingItem(**ing))
    return ingredients


def _aggregate_items(items: List[ShoppingItem]) -> Dict[str, ShoppingItem]:
    aggregated: Dict[str, ShoppingItem] = {}
    for item in items:
        key = (item.name.lower(), item.unit or "")
        if key not in aggregated:
            aggregated[key] = ShoppingItem(**item.model_dump())
        else:
            aggregated[key].quantity += item.quantity or 0
            aggregated[key].notes = aggregated[key].notes or item.notes
            aggregated[key].category = aggregated[key].category or item.category
    return aggregated


def _subtract_pantry(items: Dict[str, ShoppingItem], pantry: List[PantryItem]) -> None:
    for p in pantry:
        key = (p.name.lower(), p.unit or "")
        if key in items:
            remaining = items[key].quantity - (p.quantity or 0)
            items[key].quantity = max(0.0, remaining)
            if items[key].quantity == 0:
                items[key].notes = (items[key].notes or "") + " (pantry)"


@router.post("/shopping.generate", response_model=ShoppingListResponse)
def shopping_generate(payload: ShoppingGenerateRequest, session: Session = Depends(get_session)):
    recipe_ids: List[str] = []
    direct_items: List[ShoppingItem] = []
    if payload.plan_id:
        plan = session.get(PlanWeek, payload.plan_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        plan_data = plan.plan_json or {}
        for day in plan_data.get("days", []):
            for meal in day.get("meals", []):
                rid = meal.get("recipe_id")
                if rid:
                    recipe_ids.append(rid)
                for ing in meal.get("ingredients", []):
                    direct_items.append(ShoppingItem(**ing))
    recipe_ids.extend(payload.recipe_ids)
    recipe_ids = list(dict.fromkeys(recipe_ids))

    items = _gather_ingredients(session, recipe_ids)
    items.extend(direct_items)
    aggregated = _aggregate_items(items)

    if payload.subtract_pantry:
        pantry_items = session.exec(select(PantryItem)).all()
        _subtract_pantry(aggregated, pantry_items)

    grouped: Dict[str, List[ShoppingItem]] = defaultdict(list)
    for item in aggregated.values():
        category = item.category or "uncategorized"
        if item.quantity <= 0:
            continue
        grouped[category].append(item)

    shopping = ShoppingList(
        plan_id=payload.plan_id,
        recipe_ids=recipe_ids,
        items_json=[item.model_dump() for item in aggregated.values()],
    )
    session.add(shopping)
    session.commit()
    session.refresh(shopping)

    grouped_serializable = {
        category: [ShoppingItem(**i.model_dump()) for i in items]
        for category, items in grouped.items()
    }

    return ShoppingListResponse(list_id=shopping.id, items_by_category=grouped_serializable)
