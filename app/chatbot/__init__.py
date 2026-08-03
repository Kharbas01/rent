"""AI assistant for the Property & Rent Management app.

Rule-based, multilingual (English / Hindi / Hinglish) NLU + real-time
answers pulled straight from the tenant's own Supabase data. No external
AI API calls are made — everything runs locally using free, dependency-free
Python (stdlib `difflib` for typo tolerance), so there is nothing to
configure and no data ever leaves the server.
"""
