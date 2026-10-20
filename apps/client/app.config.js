module.exports = ({ config }) => {
  const projectId = process.env.EXPO_PUBLIC_EAS_PROJECT_ID;
  return {
    ...config,
    extra: {
      ...(config.extra || {}),
      ...(projectId ? { eas: { ...((config.extra && config.extra.eas) || {}), projectId } } : {}),
    },
  };
};
