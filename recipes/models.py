import json
import logging
from datetime import date

from django.conf import settings
from django.db import models
from django.utils.text import slugify

logger = logging.getLogger(__name__)


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Recipe(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    ingredients = models.TextField(help_text="Enter each ingredient on a new line")
    instructions = models.TextField(help_text="Enter each step on a new line")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="recipes"
    )
    prep_time = models.PositiveIntegerField(help_text="Preparation time in minutes", default=0)
    cook_time = models.PositiveIntegerField(help_text="Cooking time in minutes", default=0)
    servings = models.PositiveIntegerField(default=1)
    image = models.ImageField(upload_to="recipes/", blank=True, help_text="Upload a photo of the dish")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Nutrition fields (per serving, estimated by AI)
    calories = models.PositiveIntegerField(null=True, blank=True)
    protein_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fat_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    fiber_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    sugar_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    sodium_mg = models.PositiveIntegerField(null=True, blank=True)

    # Track which ingredients were used for the last nutrition estimate
    _ingredients_hash = models.CharField(max_length=64, blank=True, default="", db_column="ingredients_hash")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def _compute_ingredients_hash(self):
        import hashlib
        content = f"{self.ingredients}|{self.servings}"
        return hashlib.sha256(content.encode()).hexdigest()

    @property
    def has_nutrition(self):
        return self.calories is not None

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        # Check if ingredients changed since last nutrition estimate
        new_hash = self._compute_ingredients_hash()
        ingredients_changed = new_hash != self._ingredients_hash

        super().save(*args, **kwargs)

        if ingredients_changed and self.ingredients.strip():
            self._generate_nutrition(new_hash)

    def _generate_nutrition(self, ingredients_hash):
        """Call Claude API to estimate nutrition and save results."""
        api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
        if not api_key or api_key == "your-api-key-here":
            logger.warning("Skipping nutrition estimation: ANTHROPIC_API_KEY not configured")
            return

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Estimate the nutrition facts PER SERVING for this recipe "
                            f"({self.servings} serving{'s' if self.servings != 1 else ''}).\n\n"
                            f"Ingredients:\n{self.ingredients}\n\n"
                            f"Respond ONLY with a JSON object, no other text:\n"
                            f'{{"calories": <int>, "protein_g": <float>, "carbs_g": <float>, '
                            f'"fat_g": <float>, "fiber_g": <float>, "sugar_g": <float>, '
                            f'"sodium_mg": <int>}}'
                        ),
                    }
                ],
            )

            text = message.content[0].text.strip()
            # Handle cases where the response might have markdown code fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(text)

            Recipe.objects.filter(pk=self.pk).update(
                calories=int(data["calories"]),
                protein_g=round(float(data["protein_g"]), 1),
                carbs_g=round(float(data["carbs_g"]), 1),
                fat_g=round(float(data["fat_g"]), 1),
                fiber_g=round(float(data["fiber_g"]), 1),
                sugar_g=round(float(data["sugar_g"]), 1),
                sodium_mg=int(data["sodium_mg"]),
                _ingredients_hash=ingredients_hash,
            )
            logger.info("Nutrition estimated for recipe '%s'", self.title)

        except Exception:
            logger.exception("Failed to estimate nutrition for recipe '%s'", self.title)

    @property
    def total_time(self):
        return self.prep_time + self.cook_time


class PantryItem(models.Model):
    STORAGE_CHOICES = [
        ("fridge", "Refrigerator"),
        ("freezer", "Freezer"),
        ("pantry", "Pantry"),
    ]

    name = models.CharField(max_length=200)
    quantity = models.CharField(max_length=100, blank=True, help_text="e.g., 2 lbs, 1 gallon")
    storage = models.CharField(max_length=10, choices=STORAGE_CHOICES, default="fridge")
    sell_by_date = models.DateField(help_text="Sell-by or use-by date from the package")
    notes = models.TextField(blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["sell_by_date"]

    def __str__(self):
        return f"{self.name} (sell by {self.sell_by_date})"

    @property
    def days_remaining(self):
        """Days until sell-by date. Negative means past due."""
        return (self.sell_by_date - date.today()).days

    @property
    def status(self):
        """Return freshness status: 'expired', 'today', 'warning', or 'fresh'."""
        days = self.days_remaining
        if days < 0:
            return "expired"
        elif days == 0:
            return "today"
        elif days <= 2:
            return "warning"
        return "fresh"

    @property
    def status_label(self):
        labels = {
            "expired": f"Expired {abs(self.days_remaining)} day{'s' if abs(self.days_remaining) != 1 else ''} ago",
            "today": "Use today!",
            "warning": f"{self.days_remaining} day{'s' if self.days_remaining != 1 else ''} left",
            "fresh": f"{self.days_remaining} days left",
        }
        return labels[self.status]


class ShoppingItem(models.Model):
    SECTION_CHOICES = [
        ("produce", "Produce"),
        ("dairy", "Dairy"),
        ("meat", "Meat & Seafood"),
        ("bakery", "Bakery"),
        ("frozen", "Frozen"),
        ("pantry", "Pantry"),
        ("beverages", "Beverages"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=200)
    quantity = models.CharField(max_length=100, blank=True, help_text="e.g., 2 lbs, 1 dozen")
    section = models.CharField(max_length=10, choices=SECTION_CHOICES, default="other")
    checked = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["checked", "section", "name"]

    def __str__(self):
        return self.name
