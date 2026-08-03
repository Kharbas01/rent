"""Supabase client factory.

A fresh client is created per request so that each request can carry the
signed-in user's JWT (this is what makes Row Level Security work).
"""

from supabase import Client, create_client

try:  # supabase-py >= 2.4 exports ClientOptions at the top level
    from supabase import ClientOptions
except ImportError:  # pragma: no cover - fallback for older releases
    from supabase.lib.client_options import ClientOptions  # type: ignore

from app.config import get_settings


def build_client(access_token: str | None = None) -> Client:
    """Create a Supabase client, optionally authenticated as a user."""
    settings = get_settings()
    settings.raise_if_unconfigured()

    options = ClientOptions(
        auto_refresh_token=False,
        persist_session=False,
    )
    client: Client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=options,
    )

    if access_token:
        # Attach the user JWT to PostgREST + Storage so RLS applies.
        client.postgrest.auth(access_token)
    return client
