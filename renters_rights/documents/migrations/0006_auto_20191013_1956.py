# Generated by Django 2.2.6 on 2019-10-13 19:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("documents", "0005_auto_20190822_0246")]

    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="description",
            field=models.TextField(blank=True, help_text="A description of the document. This will be shown to users."),
        ),
        migrations.AddField(
            model_name="documenttemplate",
            name="description_en",
            field=models.TextField(
                blank=True, help_text="A description of the document. This will be shown to users.", null=True
            ),
        ),
        migrations.AddField(model_name="documenttemplate", name="name_en", field=models.CharField(max_length=50, null=True)),
    ]