export const Category = {
  NORMAL: 'NORMAL',
  EVENT: 'EVENT',
} as const;
export type Category = (typeof Category)[keyof typeof Category];
