# Generated by Django 2.2.3 on 2019-07-07 15:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("units", "0003_auto_20190707_1523")]

    operations = [
        migrations.RemoveField(model_name="unit", name="documents"),
        migrations.RemoveField(model_name="unit", name="images"),
        migrations.AddField(
            model_name="unitimage",
            name="unit",
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to="units.Unit"),
            preserve_default=False,
        ),
    ]
