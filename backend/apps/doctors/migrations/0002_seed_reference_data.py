from django.db import migrations

COUNCILS = ["West Bengal Medical Council", "Delhi Medical Council", "Maharashtra Medical Council",
            "Karnataka Medical Council", "National Medical Commission"]
SPECIALITIES = [
    ("general-physician", "General physician", "Fever, infections, check-ups"),
    ("paediatrics", "Paediatrics", "Child health"),
    ("dermatology", "Dermatology", "Skin and hair"),
    ("gynaecology", "Gynaecology", "Women's health"),
    ("dentistry", "Dentistry", "Teeth and gums"),
    ("orthopaedics", "Orthopaedics", "Bones and joints"),
    ("ent", "ENT", "Ear, nose and throat"),
    ("cardiology", "Cardiology", "Heart health"),
]


def seed(apps, schema_editor):
    Council, Speciality = apps.get_model("doctors", "Council"), apps.get_model("doctors", "Speciality")
    for name in COUNCILS:
        Council.objects.get_or_create(name=name)
    for slug, name, blurb in SPECIALITIES:
        Speciality.objects.get_or_create(slug=slug, defaults={"name": name, "blurb": blurb})


class Migration(migrations.Migration):
    dependencies = [("doctors", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
