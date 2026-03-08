from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0010_make_user_required"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IngredientSubstitution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ingredient_name", models.CharField(max_length=200)),
                ("substitute_name", models.CharField(max_length=200)),
                ("dietary_need", models.CharField(
                    choices=[
                        ("gluten_free", "Gluten-Free"),
                        ("keto", "Keto"),
                        ("vegan", "Vegan"),
                        ("vegetarian", "Vegetarian"),
                        ("dairy_free", "Dairy-Free"),
                        ("nut_free", "Nut-Free"),
                        ("low_sodium", "Low-Sodium"),
                        ("paleo", "Paleo"),
                        ("low_carb", "Low-Carb"),
                        ("egg_free", "Egg-Free"),
                    ],
                    max_length=20,
                )),
                ("conversion_ratio", models.CharField(blank=True, help_text="e.g., '1:1'", max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("ai_generated", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="substitutions",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "ordering": ["dietary_need", "ingredient_name"],
            },
        ),
    ]
