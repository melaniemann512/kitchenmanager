from django import forms

from .models import Category, IngredientSubstitution, PantryItem, Recipe, ShoppingItem


class IngredientSubstitutionForm(forms.ModelForm):
    class Meta:
        model  = IngredientSubstitution
        fields = ["ingredient_name", "substitute_name", "dietary_need", "conversion_ratio", "notes"]
        widgets = {
            "ingredient_name":  forms.TextInput(attrs={"placeholder": "e.g., all-purpose flour"}),
            "substitute_name":  forms.TextInput(attrs={"placeholder": "e.g., almond flour"}),
            "conversion_ratio": forms.TextInput(attrs={"placeholder": "e.g., 1:1 or 3/4 cup per cup"}),
            "notes":            forms.Textarea(attrs={"rows": 2}),
        }


class RecipeForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user)

    class Meta:
        model = Recipe
        fields = [
            "title",
            "description",
            "image",
            "ingredients",
            "instructions",
            "category",
            "prep_time",
            "cook_time",
            "servings",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Recipe title"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Brief description"}),
            "ingredients": forms.Textarea(
                attrs={"rows": 8, "placeholder": "One ingredient per line"}
            ),
            "instructions": forms.Textarea(
                attrs={"rows": 10, "placeholder": "One step per line"}
            ),
            "prep_time": forms.NumberInput(attrs={"min": 0}),
            "cook_time": forms.NumberInput(attrs={"min": 0}),
            "servings": forms.NumberInput(attrs={"min": 1}),
        }


class PantryItemForm(forms.ModelForm):
    class Meta:
        model = PantryItem
        fields = ["name", "quantity_amount", "unit", "low_stock_threshold", "storage", "sell_by_date", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Ground Beef"}),
            "quantity_amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "e.g., 5"}),
            "unit": forms.TextInput(attrs={"placeholder": "e.g., lbs, oz, cups"}),
            "low_stock_threshold": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "Auto: 25% of quantity"}),
            "sell_by_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional notes"}),
        }


class ShoppingItemForm(forms.ModelForm):
    class Meta:
        model = ShoppingItem
        fields = ["name", "quantity", "section"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Milk"}),
            "quantity": forms.TextInput(attrs={"placeholder": "e.g., 1 gallon"}),
        }
