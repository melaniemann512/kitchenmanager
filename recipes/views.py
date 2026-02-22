import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

from .forms import PantryItemForm, RecipeForm, ShoppingItemForm
from .models import Category, PantryItem, Recipe, ShoppingItem


def dashboard(request):
    # Recipes summary
    recipe_count = Recipe.objects.count()
    recent_recipes = Recipe.objects.select_related("category")[:5]

    # Pantry summary
    active_pantry = PantryItem.objects.filter(used=False)
    pantry_count = active_pantry.count()
    expiring_items = active_pantry.order_by("sell_by_date")
    urgent_items = [item for item in expiring_items if item.status in ("expired", "today", "warning")]
    low_stock_items = [item for item in active_pantry if item.is_low_stock]

    # Shopping summary
    unchecked_shopping = ShoppingItem.objects.filter(checked=False)
    shopping_count = unchecked_shopping.count()

    # Categories with recipe counts
    categories = Category.objects.annotate(recipe_count=Count("recipes"))

    return render(request, "recipes/dashboard.html", {
        "recipe_count": recipe_count,
        "recent_recipes": recent_recipes,
        "pantry_count": pantry_count,
        "urgent_items": urgent_items,
        "low_stock_items": low_stock_items,
        "shopping_count": shopping_count,
        "unchecked_shopping": unchecked_shopping,
        "categories": categories,
    })


def about(request):
    return render(request, "recipes/about.html")


def recipe_list(request):
    query = request.GET.get("q", "").strip()
    recipes = Recipe.objects.select_related("category")
    if query:
        recipes = recipes.filter(Q(title__icontains=query) | Q(ingredients__icontains=query))

    return render(request, "recipes/recipe_list.html", {
        "recipes": recipes,
        "query": query,
    })


def recipe_detail(request, slug):
    recipe = get_object_or_404(Recipe.objects.select_related("category"), slug=slug)
    return render(request, "recipes/recipe_detail.html", {"recipe": recipe})


def recipe_create(request):
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            recipe = form.save()
            return redirect("recipe_detail", slug=recipe.slug)
    else:
        form = RecipeForm()
    return render(request, "recipes/recipe_form.html", {"form": form, "editing": False})


def recipe_edit(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        if form.is_valid():
            recipe = form.save()
            return redirect("recipe_detail", slug=recipe.slug)
    else:
        form = RecipeForm(instance=recipe)
    return render(request, "recipes/recipe_form.html", {"form": form, "editing": True, "recipe": recipe})


def recipe_delete(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    if request.method == "POST":
        recipe.delete()
        return redirect("recipe_list")
    return render(request, "recipes/recipe_confirm_delete.html", {"recipe": recipe})


def category_list(request):
    categories = Category.objects.annotate(recipe_count=Count("recipes"))
    return render(request, "recipes/category_list.html", {"categories": categories})


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    recipes = category.recipes.all()
    return render(
        request, "recipes/category_detail.html", {"category": category, "recipes": recipes}
    )


def timer(request):
    minutes = request.GET.get("m", "")
    label = request.GET.get("label", "")
    return render(request, "recipes/timer.html", {"initial_minutes": minutes, "initial_label": label})


def converter(request):
    return render(request, "recipes/converter.html")


def pantry_list(request):
    show = request.GET.get("show", "active")
    if show == "all":
        items = PantryItem.objects.all()
    else:
        items = PantryItem.objects.filter(used=False)

    # Serialize quantity data as JSON for localStorage initialization
    items_json = json.dumps([
        {
            "id": item.pk,
            "quantity_amount": str(item.quantity_amount) if item.quantity_amount is not None else None,
            "unit": item.unit,
            "low_stock_threshold": str(item.low_stock_threshold) if item.low_stock_threshold is not None else None,
            "is_low_stock": item.is_low_stock,
        }
        for item in items
    ])

    return render(request, "recipes/pantry_list.html", {
        "items": items,
        "show": show,
        "items_json": items_json,
    })


def pantry_add(request):
    if request.method == "POST":
        form = PantryItemForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("pantry_list")
    else:
        form = PantryItemForm()
    return render(request, "recipes/pantry_form.html", {"form": form, "editing": False})


def pantry_edit(request, pk):
    item = get_object_or_404(PantryItem, pk=pk)
    if request.method == "POST":
        form = PantryItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect("pantry_list")
    else:
        form = PantryItemForm(instance=item)
    return render(request, "recipes/pantry_form.html", {"form": form, "editing": True, "item": item})


def pantry_mark_used(request, pk):
    item = get_object_or_404(PantryItem, pk=pk)
    if request.method == "POST":
        item.used = True
        item.save()
    return redirect("pantry_list")


def pantry_delete(request, pk):
    item = get_object_or_404(PantryItem, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("pantry_list")
    return render(request, "recipes/pantry_confirm_delete.html", {"item": item})


@require_POST
def pantry_reduce_quantity(request, pk):
    item = get_object_or_404(PantryItem, pk=pk)

    if item.quantity_amount is None:
        return JsonResponse({"error": "Item has no numeric quantity"}, status=400)

    try:
        amount = Decimal(request.POST.get("amount", "1"))
    except (InvalidOperation, TypeError):
        return JsonResponse({"error": "Invalid amount"}, status=400)

    reached_zero = False
    added_to_shopping = False
    became_low_stock = False

    if amount > 0:
        # Capture state before reduction
        was_low_stock = item.is_low_stock
        # Reduce quantity
        reached_zero = item.reduce_quantity(amount)
        if reached_zero:
            exists = ShoppingItem.objects.filter(name__iexact=item.name, checked=False).exists()
            if not exists:
                ShoppingItem.objects.create(name=item.name, quantity=item.unit)
                added_to_shopping = True
        elif item.is_low_stock and not was_low_stock:
            became_low_stock = True
            exists = ShoppingItem.objects.filter(name__iexact=item.name, checked=False).exists()
            if not exists:
                ShoppingItem.objects.create(name=item.name, quantity=item.unit)
                added_to_shopping = True
    elif amount < 0:
        # Increase quantity (add back)
        item.quantity_amount = item.quantity_amount + abs(amount)
        if item.used and item.quantity_amount > 0:
            item.used = False
        item.save()

    return JsonResponse({
        "quantity_amount": str(item.quantity_amount),
        "unit": item.unit,
        "reached_zero": reached_zero,
        "added_to_shopping": added_to_shopping,
        "is_low_stock": item.is_low_stock,
        "low_stock_threshold": str(item.low_stock_threshold) if item.low_stock_threshold is not None else None,
        "became_low_stock": became_low_stock,
    })


def shopping_list(request):
    show = request.GET.get("show", "active")
    if show == "all":
        items = ShoppingItem.objects.all()
    else:
        items = ShoppingItem.objects.filter(checked=False)
    return render(request, "recipes/shopping_list.html", {"items": items, "show": show})


def shopping_add(request):
    if request.method == "POST":
        form = ShoppingItemForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("shopping_list")
    else:
        form = ShoppingItemForm()
    return render(request, "recipes/shopping_form.html", {"form": form, "editing": False})


def shopping_edit(request, pk):
    item = get_object_or_404(ShoppingItem, pk=pk)
    if request.method == "POST":
        form = ShoppingItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect("shopping_list")
    else:
        form = ShoppingItemForm(instance=item)
    return render(request, "recipes/shopping_form.html", {"form": form, "editing": True, "item": item})


def shopping_toggle(request, pk):
    item = get_object_or_404(ShoppingItem, pk=pk)
    if request.method == "POST":
        item.checked = not item.checked
        item.save()
    return redirect("shopping_list")


def shopping_delete(request, pk):
    item = get_object_or_404(ShoppingItem, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("shopping_list")
    return render(request, "recipes/shopping_confirm_delete.html", {"item": item})


def shopping_clear(request):
    if request.method == "POST":
        ShoppingItem.objects.filter(checked=True).delete()
    return redirect("shopping_list")


def recipe_generate(request):
    context = {}

    if request.method == "POST" and "save" in request.POST:
        # Save the previewed recipe
        recipe = Recipe(
            title=request.POST["title"],
            description=request.POST.get("description", ""),
            ingredients=request.POST["ingredients"],
            instructions=request.POST["instructions"],
            prep_time=int(request.POST.get("prep_time", 0)),
            cook_time=int(request.POST.get("cook_time", 0)),
            servings=int(request.POST.get("servings", 1)),
        )
        recipe.save()
        return redirect("recipe_detail", slug=recipe.slug)

    if request.method == "POST" and "query" in request.POST:
        query = request.POST["query"].strip()
        context["query"] = query

        api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
        if not api_key or api_key == "your-api-key-here":
            context["error"] = "Anthropic API key is not configured."
        else:
            try:
                import anthropic

                client = anthropic.Anthropic(api_key=api_key)
                message = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1500,
                    tools=[{"type": "web_search_20250305"}],
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Search the web for a recipe for: {query}\n\n"
                                f"Find a real recipe from a popular cooking website. "
                                f"Return ONLY a JSON object (no markdown fences, no extra text) with these fields:\n"
                                f'{{"title": "...", "description": "A 1-2 sentence description", '
                                f'"ingredients": "ingredient 1\\ningredient 2\\n...", '
                                f'"instructions": "step 1\\nstep 2\\n...", '
                                f'"prep_time": <int minutes>, "cook_time": <int minutes>, '
                                f'"servings": <int>, "source_url": "https://..."}}'
                            ),
                        }
                    ],
                )

                # Extract the text block from the response
                text = ""
                for block in message.content:
                    if block.type == "text":
                        text = block.text.strip()
                        break

                # Handle markdown code fences
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

                data = json.loads(text)
                context["recipe"] = data

            except json.JSONDecodeError:
                logger.exception("Failed to parse AI recipe response")
                context["error"] = "Could not parse the recipe. Please try again."
            except Exception:
                logger.exception("Failed to generate recipe")
                context["error"] = "Something went wrong searching for that recipe. Please try again."

    return render(request, "recipes/recipe_generate.html", context)
