log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(asctime)s [ACCESS] - %(client_addr)s - "%(request_line)s" %(status_code)s',
            "use_colors": True,
        },
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "use_colors": True,
        },
    },
    "handlers": {
        "access": {
            "class": "logging.StreamHandler",
            "formatter": "access",
        },
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        # "root": {
        #     "handlers": ["default"],
        #     "level": settings.app_log_level,
        # },
        "uvicorn": {"handlers": ["default"], "level": "DEBUG", "propagate": True},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO", "propagate": False},
    },
}
