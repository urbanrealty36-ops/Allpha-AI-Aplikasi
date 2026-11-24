-- ENG-P09 forward repair: persist the capability already required by the
-- Model Cost API and route policy. Existing production row is the Qwen text model.
alter table public.ai_model_cost_configs
  add column if not exists capability text;

do $migration$
begin
  if exists (
    select 1
    from public.ai_model_cost_configs
    where capability is null
      and not (
        provider_id = 'nvidia-nim'
        and model_id = 'qwen/qwen2.5-coder-32b-instruct'
        and model_version = 'qwen/qwen2.5-coder-32b-instruct'
      )
  ) then
    raise exception 'ENG_P09_CAPABILITY_BACKFILL_REQUIRES_EXPLICIT_CLASSIFICATION';
  end if;
end;
$migration$;

update public.ai_model_cost_configs
set capability = 'text_generation'
where capability is null
  and provider_id = 'nvidia-nim'
  and model_id = 'qwen/qwen2.5-coder-32b-instruct'
  and model_version = 'qwen/qwen2.5-coder-32b-instruct';

do $migration$
begin
  if exists (select 1 from public.ai_model_cost_configs where capability is null) then
    raise exception 'ENG_P09_CAPABILITY_NULL_ROWS_REMAIN';
  end if;
end;
$migration$;

alter table public.ai_model_cost_configs
  alter column capability set default 'text_generation',
  alter column capability set not null;

alter table public.ai_model_cost_configs
  drop constraint if exists ai_model_cost_capability_valid;
alter table public.ai_model_cost_configs
  add constraint ai_model_cost_capability_valid
  check (capability in ('text_generation','embedding','image_generation','video_generation','reranking'));

create index if not exists ai_model_cost_approved_capability_route_idx
  on public.ai_model_cost_configs(capability,provider_id,model_id,model_version,policy_version)
  where status='active' and policy_approved=true;

comment on column public.ai_model_cost_configs.capability is
  'Explicit model capability used to bind provider/model/version/pricing/policy to one routed operation.';
