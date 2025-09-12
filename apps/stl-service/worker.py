import os, time, json, tempfile
import cadquery as cq
from utils.storage import upload_to_supabase
from models.vesa_adapter import build as vesa_adapter
from models.router_mount import build as router_mount
from models.cable_tray import build as cable_tray
from supabase import create_client

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
BUCKET = os.getenv('SUPABASE_BUCKET', 'forge-stl')

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def process_job(job):
    job_id = job['id']
    params = job['params']
    slug = job['model_slug']
    order_id = job['order_id']

    # mark processing
    sb.table('stl_jobs').update({'status':'processing'}).eq('id', job_id).execute()

    try:
        if slug == 'vesa-adapter':
            part = vesa_adapter(**params)
        elif slug == 'router-mount':
            part = router_mount(**params)
        elif slug == 'cable-tray':
            part = cable_tray(**params)
        else:
            raise ValueError('Unknown model_slug')

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, f"{slug}-{order_id}.stl")
            cq.exporters.export(part, path)
            url = upload_to_supabase(path, BUCKET, f"{order_id}/{os.path.basename(path)}")

        sb.table('stl_jobs').update({'status':'done','stl_path': url}).eq('id', job_id).execute()
        print("Processed", job_id)
    except Exception as e:
        sb.table('stl_jobs').update({'status':'error','error': str(e)}).eq('id', job_id).execute()
        print("Error in job", job_id, e)

def loop():
    while True:
        # fetch oldest queued job
        res = sb.table('stl_jobs').select('*').eq('status','queued').order('created_at', asc=True).limit(1).execute()
        data = res.data or []
        if data:
            process_job(data[0])
        else:
            time.sleep(2)  # backoff

if __name__ == '__main__':
    loop()