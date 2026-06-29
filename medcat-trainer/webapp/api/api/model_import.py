import os
from datetime import datetime, timezone

from django.core.files import File

from api.extensions import dispatch, model_pack_imported
from api.models import ModelPack


class ImportModelPackError(Exception):
    """Raised when a model pack cannot be registered from a source archive."""


def import_model_pack(src_zip, *, name, user=None, description=None, source_uri=None):
    """Register a model pack zip already on disk as a new ModelPack.

    Copies ``src_zip`` into ``MEDIA_ROOT``, unpacks/links CDB/Vocab via
    ``ModelPack.save()``, and emits ``model_pack_imported``.
    """
    stripped_name = (name or '').strip()
    if not stripped_name:
        raise ImportModelPackError('Model pack name is required.')

    if ModelPack.objects.filter(name=stripped_name).exists():
        raise ImportModelPackError(f'A model pack named "{stripped_name}" already exists.')

    if not os.path.isfile(src_zip):
        raise ImportModelPackError(f'Model pack archive not found: {src_zip}')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
    dest_name = f'modelpacks/{stripped_name}-{stamp}.zip'

    model_pack = ModelPack(name=stripped_name, last_modified_by=user)
    with open(src_zip, 'rb') as fh:
        model_pack.model_pack.save(dest_name, File(fh), save=False)
    model_pack.save()

    dispatch(
        model_pack_imported,
        model_pack=model_pack,
        user=user,
        description=description,
        source_uri=source_uri,
    )
    return model_pack
