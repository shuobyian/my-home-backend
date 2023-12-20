import { Material } from 'src/result/type/Material';

export function makeBasic({
  material,
  endMaterials,
  count = 1,
}: {
  material: Material;
  endMaterials: Material[];
  count?: number;
}) {
  const newMaterial = { ...material, count: count * material.count };

  const mIndex = endMaterials.findIndex((b) => b.name === material.name);
  if (mIndex !== -1) {
    endMaterials[mIndex].count += count * material.count;
  } else {
    endMaterials.push(newMaterial);
  }
}
