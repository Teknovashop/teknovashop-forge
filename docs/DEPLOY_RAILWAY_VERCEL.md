# Deploy guide (Railway + Vercel)

## Railway (stl-service)
- Create a new project → Deploy from GitHub (connect this repo).
- Service Settings:
  - Root Directory: `apps/stl-service`
  - Healthcheck Path: `/health`
- Environment Variables:
  - SUPABASE_URL = https://<your-ref>.supabase.co
  - SUPABASE_SERVICE_KEY = <service role key>
  - SUPABASE_BUCKET = forge-stl
  - WATERMARK_TEXT = Teknovashop

## Vercel (web)
- Import GitHub repo.
- Root Directory: `apps/web`
- Env Vars:
  - NEXT_PUBLIC_SUPABASE_URL
  - NEXT_PUBLIC_SUPABASE_ANON_KEY
  - STL_SERVICE_URL (Railway URL)
  - DOWNLOAD_SIGNING_SECRET=changeme
