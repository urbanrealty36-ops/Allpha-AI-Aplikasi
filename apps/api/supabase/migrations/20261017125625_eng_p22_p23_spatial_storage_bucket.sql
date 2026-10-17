-- ENG-P22/ENG-P23: private canonical GLB asset bucket.
-- Keep all spatial objects private; the FastAPI service issues short-lived signed URLs.
-- Never enable public bucket access as a shortcut for the renderer.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'allpha-spatial-assets',
  'allpha-spatial-assets',
  false,
  536870912,
  array['model/gltf-binary', 'application/octet-stream']::text[]
)
on conflict (id) do nothing;
