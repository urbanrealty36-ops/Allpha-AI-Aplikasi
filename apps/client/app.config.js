// Resolve the existing EAS project binding at build time without committing project credentials.
// The EAS project ID is metadata, not a secret; all service-role keys remain server-only.
module.exports = ({ config }) => {
  const projectId =
    process.env.EAS_PROJECT_ID ||
    process.env.EXPO_PUBLIC_EAS_PROJECT_ID ||
    config.extra?.eas?.projectId;

  return {
    ...config,
    extra: {
      ...(config.extra || {}),
      ...(projectId
        ? { eas: { ...(config.extra?.eas || {}), projectId } }
        : {}),
    },
  };
};
