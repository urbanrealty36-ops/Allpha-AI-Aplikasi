module.exports = ({ config }) => {
  // EAS_PROJECT_ID is a non-secret repository/environment variable. Keep the
  // legacy EXPO_PUBLIC name as a backwards-compatible fallback for existing builds.
  const projectId =
    process.env.EAS_PROJECT_ID ||
    process.env.EXPO_PUBLIC_EAS_PROJECT_ID ||
    (config.extra && config.extra.eas && config.extra.eas.projectId);
  return {
    ...config,
    extra: {
      ...(config.extra || {}),
      ...(projectId ? { eas: { ...((config.extra && config.extra.eas) || {}), projectId } } : {}),
    },
  };
};
