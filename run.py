"""Entry point for the Rent Management System.

Usage:
    python run.py
"""

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    print("=" * 60)
    print(f"  {settings.app_name} - Rent Management System")
    print(f"  Open your browser at: http://{settings.host}:{settings.port}")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
