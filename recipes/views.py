import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

from .forms import IngredientSubstitutionForm, PantryItemForm, RecipeForm, ShoppingItemForm
from .models import Category, IngredientSubstitution, PantryItem, Recipe, ShoppingItem


# ── Auth views ────────────────────────────────────────────────────────────────

def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("dashboard")
    else:
        form = UserCreationForm()
    return render(request, "recipes/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            next_url = request.GET.get("next", "")
            return redirect(next_url if next_url else "dashboard")
    else:
        form = AuthenticationForm()
    return render(request, "recipes/login.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        auth_logout(request)
    return redirect("login")


# ── Public views ──────────────────────────────────────────────────────────────

def about(request):
    return render(request, "recipes/about.html")


def timer(request):
    minutes = request.GET.get("m", "")
    label = request.GET.get("label", "")
    return render(request, "recipes/timer.html", {"initial_minutes": minutes, "initial_label": label})


def converter(request):
    return render(request, "recipes/converter.html")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    recipe_count = Recipe.objects.filter(user=request.user).count()
    recent_recipes = Recipe.objects.filter(user=request.user).select_related("category")[:5]

    active_pantry = PantryItem.objects.filter(user=request.user, used=False)
    pantry_count = active_pantry.count()
    expiring_items = active_pantry.order_by("sell_by_date")
    urgent_items = [item for item in expiring_items if item.status in ("expired", "today", "warning")]
    low_stock_items = [item for item in active_pantry if item.is_low_stock]

    unchecked_shopping = ShoppingItem.objects.filter(user=request.user, checked=False)
    shopping_count = unchecked_shopping.count()

    categories = Category.objects.filter(user=request.user).annotate(recipe_count=Count("recipes"))

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


# ── Recipe views ──────────────────────────────────────────────────────────────

@login_required
def recipe_list(request):
    query = request.GET.get("q", "").strip()
    recipes = Recipe.objects.filter(user=request.user).select_related("category")
    if query:
        recipes = recipes.filter(Q(title__icontains=query) | Q(ingredients__icontains=query))
    return render(request, "recipes/recipe_list.html", {"recipes": recipes, "query": query})


@login_required
def recipe_detail(request, slug):
    recipe = get_object_or_404(
        Recipe.objects.select_related("category"), slug=slug, user=request.user
    )
    return render(request, "recipes/recipe_detail.html", {"recipe": recipe})


@login_required
def recipe_create(request):
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.user = request.user
            recipe.save()
            return redirect("recipe_detail", slug=recipe.slug)
    else:
        form = RecipeForm(user=request.user)
    return render(request, "recipes/recipe_form.html", {"form": form, "editing": False})


@login_required
def recipe_edit(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, user=request.user)
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, instance=recipe, user=request.user)
        if form.is_valid():
            recipe = form.save()
            return redirect("recipe_detail", slug=recipe.slug)
    else:
        form = RecipeForm(instance=recipe, user=request.user)
    return render(request, "recipes/recipe_form.html", {"form": form, "editing": True, "recipe": recipe})


@login_required
def recipe_delete(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, user=request.user)
    if request.method == "POST":
        recipe.delete()
        return redirect("recipe_list")
    return render(request, "recipes/recipe_confirm_delete.html", {"recipe": recipe})


@login_required
def recipe_generate(request):
    context = {}

    if request.method == "POST" and "save" in request.POST:
        recipe = Recipe(
            user=request.user,
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

                text = ""
                for block in message.content:
                    if block.type == "text":
                        text = block.text.strip()
                        break

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


# ── Category views ────────────────────────────────────────────────────────────

@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user).annotate(recipe_count=Count("recipes"))
    return render(request, "recipes/category_list.html", {"categories": categories})


@login_required
def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, user=request.user)
    recipes = category.recipes.filter(user=request.user)
    return render(request, "recipes/category_detail.html", {"category": category, "recipes": recipes})


# ── Pantry views ──────────────────────────────────────────────────────────────

@login_required
def pantry_list(request):
    show = request.GET.get("show", "active")
    if show == "all":
        items = PantryItem.objects.filter(user=request.user)
    else:
        items = PantryItem.objects.filter(user=request.user, used=False)

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


@login_required
def pantry_add(request):
    if request.method == "POST":
        form = PantryItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            return redirect("pantry_list")
    else:
        form = PantryItemForm()
    return render(request, "recipes/pantry_form.html", {"form": form, "editing": False})


@login_required
def pantry_edit(request, pk):
    item = get_object_or_404(PantryItem, pk=pk, user=request.user)
    if request.method == "POST":
        form = PantryItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect("pantry_list")
    else:
        form = PantryItemForm(instance=item)
    return render(request, "recipes/pantry_form.html", {"form": form, "editing": True, "item": item})


@login_required
def pantry_mark_used(request, pk):
    item = get_object_or_404(PantryItem, pk=pk, user=request.user)
    if request.method == "POST":
        item.used = True
        item.save()
    return redirect("pantry_list")


@login_required
def pantry_delete(request, pk):
    item = get_object_or_404(PantryItem, pk=pk, user=request.user)
    if request.method == "POST":
        item.delete()
        return redirect("pantry_list")
    return render(request, "recipes/pantry_confirm_delete.html", {"item": item})


@login_required
@require_POST
def pantry_reduce_quantity(request, pk):
    item = get_object_or_404(PantryItem, pk=pk, user=request.user)

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
        was_low_stock = item.is_low_stock
        reached_zero = item.reduce_quantity(amount)
        if reached_zero:
            exists = ShoppingItem.objects.filter(
                user=request.user, name__iexact=item.name, checked=False
            ).exists()
            if not exists:
                ShoppingItem.objects.create(user=request.user, name=item.name, quantity=item.unit)
                added_to_shopping = True
        elif item.is_low_stock and not was_low_stock:
            became_low_stock = True
            exists = ShoppingItem.objects.filter(
                user=request.user, name__iexact=item.name, checked=False
            ).exists()
            if not exists:
                ShoppingItem.objects.create(user=request.user, name=item.name, quantity=item.unit)
                added_to_shopping = True
    elif amount < 0:
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


# ── Shopping views ────────────────────────────────────────────────────────────

@login_required
def shopping_list(request):
    show = request.GET.get("show", "active")
    if show == "all":
        items = ShoppingItem.objects.filter(user=request.user)
    else:
        items = ShoppingItem.objects.filter(user=request.user, checked=False)
    return render(request, "recipes/shopping_list.html", {"items": items, "show": show})


@login_required
def shopping_add(request):
    if request.method == "POST":
        form = ShoppingItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.user = request.user
            item.save()
            return redirect("shopping_list")
    else:
        form = ShoppingItemForm()
    return render(request, "recipes/shopping_form.html", {"form": form, "editing": False})


@login_required
def shopping_edit(request, pk):
    item = get_object_or_404(ShoppingItem, pk=pk, user=request.user)
    if request.method == "POST":
        form = ShoppingItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect("shopping_list")
    else:
        form = ShoppingItemForm(instance=item)
    return render(request, "recipes/shopping_form.html", {"form": form, "editing": True, "item": item})


@login_required
def shopping_toggle(request, pk):
    item = get_object_or_404(ShoppingItem, pk=pk, user=request.user)
    if request.method == "POST":
        item.checked = not item.checked
        item.save()
    return redirect("shopping_list")


@login_required
def shopping_delete(request, pk):
    item = get_object_or_404(ShoppingItem, pk=pk, user=request.user)
    if request.method == "POST":
        item.delete()
        return redirect("shopping_list")
    return render(request, "recipes/shopping_confirm_delete.html", {"item": item})


@login_required
def shopping_clear(request):
    if request.method == "POST":
        ShoppingItem.objects.filter(user=request.user, checked=True).delete()
    return redirect("shopping_list")


# ── Substitution views ────────────────────────────────────────────────────────

@login_required
def substitution_list(request):
    dietary_need = request.GET.get("dietary_need", "")

    global_qs = IngredientSubstitution.objects.filter(user__isnull=True)
    user_qs = IngredientSubstitution.objects.filter(user=request.user)

    if dietary_need:
        global_qs = global_qs.filter(dietary_need=dietary_need)
        user_qs = user_qs.filter(dietary_need=dietary_need)

    if request.method == "POST":
        form = IngredientSubstitutionForm(request.POST)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.user = request.user
            sub.save()
            return redirect("substitution_list")
    else:
        form = IngredientSubstitutionForm()

    return render(request, "recipes/substitution_list.html", {
        "global_subs": global_qs,
        "user_subs": user_qs,
        "form": form,
        "dietary_need": dietary_need,
        "dietary_choices": IngredientSubstitution.DIETARY_CHOICES,
    })


@login_required
@require_POST
def substitution_lookup(request):
    ingredient = request.POST.get("ingredient", "").strip()
    dietary_need = request.POST.get("dietary_need", "").strip()

    if not ingredient or not dietary_need:
        return JsonResponse({"error": "ingredient and dietary_need are required"}, status=400)

    # 1. Check user override
    user_sub = IngredientSubstitution.objects.filter(
        user=request.user,
        ingredient_name__iexact=ingredient,
        dietary_need=dietary_need,
    ).first()
    if user_sub:
        return JsonResponse({
            "substitute_name": user_sub.substitute_name,
            "conversion_ratio": user_sub.conversion_ratio,
            "notes": user_sub.notes,
            "source": "user",
        })

    # 2. Check global cache
    global_sub = IngredientSubstitution.objects.filter(
        user__isnull=True,
        ingredient_name__iexact=ingredient,
        dietary_need=dietary_need,
    ).first()
    if global_sub:
        return JsonResponse({
            "substitute_name": global_sub.substitute_name,
            "conversion_ratio": global_sub.conversion_ratio,
            "notes": global_sub.notes,
            "source": "global_cache",
        })

    # 3. Call Claude API
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        return JsonResponse({"error": "AI not configured"}, status=503)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        dietary_label = dict(IngredientSubstitution.DIETARY_CHOICES).get(dietary_need, dietary_need)
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"What is the best {dietary_label} substitute for \"{ingredient}\"? "
                    f"Respond ONLY with a JSON object, no other text:\n"
                    f'{{"substitute_name": "...", "conversion_ratio": "...", "notes": "..."}}'
                ),
            }],
        )
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(text)

        IngredientSubstitution.objects.create(
            user=None,
            ingredient_name=ingredient,
            substitute_name=data["substitute_name"],
            dietary_need=dietary_need,
            conversion_ratio=data.get("conversion_ratio", ""),
            notes=data.get("notes", ""),
            ai_generated=True,
        )

        return JsonResponse({
            "substitute_name": data["substitute_name"],
            "conversion_ratio": data.get("conversion_ratio", ""),
            "notes": data.get("notes", ""),
            "source": "ai",
        })

    except Exception:
        logger.exception("substitution_lookup failed")
        return JsonResponse({"error": "Failed to look up substitution"}, status=500)


@login_required
@require_POST
def substitution_delete(request, pk):
    sub = get_object_or_404(IngredientSubstitution, pk=pk, user=request.user)
    sub.delete()
    return redirect("substitution_list")


@login_required
def recipe_convert(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug, user=request.user)

    if request.method == "GET":
        return render(request, "recipes/recipe_convert.html", {
            "recipe": recipe,
            "dietary_choices": IngredientSubstitution.DIETARY_CHOICES,
        })

    dietary_need = request.POST.get("dietary_need", "").strip()
    if not dietary_need:
        return render(request, "recipes/recipe_convert.html", {
            "recipe": recipe,
            "dietary_choices": IngredientSubstitution.DIETARY_CHOICES,
            "error": "Please select a dietary need.",
        })

    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        return render(request, "recipes/recipe_convert.html", {
            "recipe": recipe,
            "dietary_choices": IngredientSubstitution.DIETARY_CHOICES,
            "error": "AI is not configured. Cannot convert recipe.",
        })

    lines = [l for l in recipe.ingredients.splitlines() if l.strip()]

    try:
        import re
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Step 1: Extract clean ingredient names from raw lines
        lines_text = "\n".join(f"- {l}" for l in lines)
        extract_msg = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": (
                    f"Extract the clean ingredient name (no quantity, no prep method) from each line below. "
                    f"Return ONLY a JSON array of strings in the same order:\n{lines_text}"
                ),
            }],
        )
        text = extract_msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        ingredient_names = json.loads(text)

        # Step 2: For each ingredient, check cache; collect missing
        dietary_label = dict(IngredientSubstitution.DIETARY_CHOICES).get(dietary_need, dietary_need)
        substitution_map = {}
        missing = []

        for name in ingredient_names:
            user_sub = IngredientSubstitution.objects.filter(
                user=request.user, ingredient_name__iexact=name, dietary_need=dietary_need
            ).first()
            if user_sub:
                substitution_map[name] = user_sub.substitute_name
                continue
            global_sub = IngredientSubstitution.objects.filter(
                user__isnull=True, ingredient_name__iexact=name, dietary_need=dietary_need
            ).first()
            if global_sub:
                substitution_map[name] = global_sub.substitute_name
            else:
                missing.append(name)

        # Step 3: Batch Claude call for all missing ingredients
        if missing:
            missing_list = ", ".join(f'"{m}"' for m in missing)
            batch_msg = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=800,
                messages=[{
                    "role": "user",
                    "content": (
                        f"For each ingredient below, provide the best {dietary_label} substitute. "
                        f"Return ONLY a JSON object mapping each ingredient name to "
                        f'{{\"substitute_name\": \"...\", \"conversion_ratio\": \"...\", \"notes\": \"...\"}}:\n'
                        f"[{missing_list}]"
                    ),
                }],
            )
            text = batch_msg.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            batch_data = json.loads(text)

            for name, info in batch_data.items():
                IngredientSubstitution.objects.create(
                    user=None,
                    ingredient_name=name,
                    substitute_name=info["substitute_name"],
                    dietary_need=dietary_need,
                    conversion_ratio=info.get("conversion_ratio", ""),
                    notes=info.get("notes", ""),
                    ai_generated=True,
                )
                substitution_map[name] = info["substitute_name"]

        # Step 4: Apply substitutions to raw ingredient lines
        new_lines = []
        for line, name in zip(lines, ingredient_names):
            sub = substitution_map.get(name)
            if sub:
                new_line = re.sub(re.escape(name), sub, line, flags=re.IGNORECASE)
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        # Step 5: Build new recipe with collision-safe slug
        new_title = f"{recipe.title} ({dietary_label})"
        base_slug = slugify(new_title)
        new_slug = base_slug
        counter = 1
        while Recipe.objects.filter(user=request.user, slug=new_slug).exists():
            new_slug = f"{base_slug}-{counter}"
            counter += 1

        new_recipe = Recipe(
            user=request.user,
            title=new_title,
            slug=new_slug,
            description=recipe.description,
            ingredients="\n".join(new_lines),
            instructions=recipe.instructions,
            category=recipe.category,
            prep_time=recipe.prep_time,
            cook_time=recipe.cook_time,
            servings=recipe.servings,
        )
        new_recipe.save()
        return redirect("recipe_detail", slug=new_recipe.slug)

    except Exception:
        logger.exception("recipe_convert failed")
        return render(request, "recipes/recipe_convert.html", {
            "recipe": recipe,
            "dietary_choices": IngredientSubstitution.DIETARY_CHOICES,
            "error": "Something went wrong converting the recipe. Please try again.",
        })
