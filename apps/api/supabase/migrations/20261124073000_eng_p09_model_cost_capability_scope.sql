-- ENG-P09: bind every tariff approval to one explicit Model Router capability.
-- Existing tariff rows are preserved as text_generation; new embedding policies
-- must be separately configured and approved before the embedding router can run.
begin;
alter table public.ai_model_cost_configs
  add column if not exists capability text not null default 'text_generation';
alter table public.ai_model_cost_configs
  drop constraint if exists ai_model_cost_configs_capability_check;
alter table public.ai_model_cost_configs
  add constraint ai_model_cost_configs_capability_check
  check (capability in ('text_generation','embedding','image_generation','video_generation','reranking'));
create index if not exists ai_model_cost_configs_capability_route_idx
  on public.ai_model_cost_configs(capability,provider_id,model_id,model_version,status);
commit;
