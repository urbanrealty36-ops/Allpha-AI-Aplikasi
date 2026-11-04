-- ENG-P21: explicitly allow the spatial governance moderation scope.
-- Existing grants are immutable; this only expands the validated scope contract.
ALTER TABLE public.platform_operator_grants
  DROP CONSTRAINT IF EXISTS platform_operator_grants_scopes_check;

ALTER TABLE public.platform_operator_grants
  ADD CONSTRAINT platform_operator_grants_scopes_check
  CHECK (
    cardinality(scopes) > 0
    AND scopes <@ ARRAY[
      'platform:operations.read',
      'platform:security.audit.read',
      'platform:capabilities.review',
      'platform:capabilities.review.high_risk',
      'platform:operators.manage',
      'platform:content.moderate'
    ]::text[]
  );

COMMENT ON CONSTRAINT platform_operator_grants_scopes_check
  ON public.platform_operator_grants IS
  'Allow-listed platform operator scopes; content moderation is used by ENG-P21 spatial governance.';
