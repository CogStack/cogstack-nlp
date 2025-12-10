from medcat_service.config import ObservabilitySettings

settings = ObservabilitySettings()
if settings.enable_tracing:
    # Initialise telemetry before any other imports
    from opentelemetry.instrumentation import auto_instrumentation

    auto_instrumentation.initialize()
