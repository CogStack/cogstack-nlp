import sys, os, secrets
import django
from django.core.files import File
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
django.setup()

# ── Import models ─────────────────────────────────────────────────────────────
try:
    from demo.models import MedcatModel, APIKey
except ImportError as e:
    print(f"[SEED] ImportError: {e}", file=sys.stderr)
    sys.exit(1)

def main(model_path: str, model_name: str, model_display_name: str,
         model_description: str, api_key_identifier: str):
    # ── MedcatModel ───────────────────────────────────────────────────────────────
    if not os.path.exists(model_path):
        print(f"[SEED] ERROR: model file not found in container: {model_path}", file=sys.stderr)
        sys.exit(1)

    obj, created = MedcatModel.objects.get_or_create(
        model_name=model_name,
        defaults={
            "model_display_name": model_display_name,
            "model_description":  model_description,
        },
    )
    if created or not obj.model_file:
        with open(model_path, "rb") as f:
            obj.model_file.save(os.path.basename(model_path), File(f), save=True)
        print(f"[SEED] MedcatModel created: {obj.model_name}", file=sys.stderr)
    else:
        print(f"[SEED] MedcatModel already exists: {obj.model_name}", file=sys.stderr)

    # ── APIKey ────────────────────────────────────────────────────────────────────
    key_value = secrets.token_hex(32)   # 64-char hex, fits max_length=64
    APIKey.objects.create(
        key=key_value,
        identifier=api_key_identifier,
        expires_at=timezone.now() + timedelta(hours=1),
        is_active=True,
    )
    print(f"[SEED] APIKey created for identifier: {api_key_identifier}", file=sys.stderr)

    # Print ONLY the key to stdout so the shell can capture it cleanly
    print(key_value)


if __name__ == "__main__":
    main(*sys.argv[1:])
