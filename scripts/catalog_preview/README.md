# Local mobile catalogue preview (test data only)

This fixture and preview API are for checking mobile discovery wiring only. The CSV contains synthetic records, explicitly marked `TEST ONLY`; it is not merchant data, approved inventory, a product-rights record, or a production import file. The API is read-only, serves only this CSV, and binds exclusively to `127.0.0.1`.

From the repository root, start the local adapter:

```powershell
python scripts/catalog_preview/server.py
```

In a second PowerShell window, set the API URL for Metro before starting Expo:

```powershell
$env:EXPO_PUBLIC_API_URL = 'http://127.0.0.1:8010'
pnpm --filter mobile web
```

Open `http://localhost:8083/discover`. The card titles and brand labels say `TEST ONLY`. To return to the ordinary not-connected UI, stop Expo and restart it without `EXPO_PUBLIC_API_URL`.

The adapter does not connect to PostgreSQL, Redis, Supabase, Auth0, or any external host. It does not test CSV ingestion, database persistence, authentication, publication, or merchant/image rights enforcement. Stop it with Ctrl+C when finished.
