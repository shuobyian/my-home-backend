import { Material } from 'src/result/type/Material';

export function makeBasic({
  material,
  materials,
  count = 1,
}: {
  material: Material;
  materials: Material[];
  count?: number;
}) {
  const newMaterial = { ...material, count: count * material.count };

  const mIndex = materials.findIndex((b) => b.name === material.name);
  if (mIndex !== -1) {
    materials[mIndex].count += count * material.count;
  } else {
    materials.push(newMaterial);
  }
}
