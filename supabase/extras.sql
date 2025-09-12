-- Add helpful indexes for job processing
create index if not exists stl_jobs_status_created_idx on public.stl_jobs(status, created_at);