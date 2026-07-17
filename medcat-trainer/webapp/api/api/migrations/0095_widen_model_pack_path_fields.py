from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0094_alter_project_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conceptdb',
            name='cdb_file',
            field=models.FileField(max_length=255, upload_to=''),
        ),
        migrations.AlterField(
            model_name='metacatmodel',
            name='meta_cat_dir',
            field=models.FilePathField(
                allow_folders=True,
                editable=False,
                help_text='The zip or dir for a MetaCAT model, not editable, is set via a model pack .zip upload',
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name='modelpack',
            name='model_pack',
            field=models.FileField(help_text='Model pack zip', max_length=255, upload_to=''),
        ),
        migrations.AlterField(
            model_name='vocabulary',
            name='vocab_file',
            field=models.FileField(max_length=255, upload_to=''),
        ),
    ]
