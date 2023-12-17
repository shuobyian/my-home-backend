export const Tool = {
  WOOD: 'WOOD',
  FIRE_PIT: 'FIRE_PIT',
  SEWING_MACHINE: 'SEWING_MACHINE',
  LEATHER: 'LEATHER',
  BRAZIER: 'BRAZIER',
  POTTERY_WHEEL: 'POTTERY_WHEEL',
  ALCHEMY_KETTLE: 'ALCHEMY_KETTLE',
} as const;
export type Tool = (typeof Tool)[keyof typeof Tool];
