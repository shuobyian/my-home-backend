import { BadRequestException } from '@nestjs/common';
import { CreateItemDto } from 'src/item/dto/create-item-dto';
import { Market } from 'src/market/entities/market.entity';
import { Result } from 'src/result/entities/result.entity';
import { Material } from 'src/result/type/Material';

export function makeBase({
  material,
  materialList,
  count = 1,
}: {
  material: Material;
  materialList: Material[];
  count?: number;
}) {
  const newMaterial = { ...material, count: count * material.count };

  const mIndex = materialList.findIndex((b) => b.name === material.name);
  if (mIndex !== -1) {
    materialList[mIndex].count += count * material.count;
  } else {
    materialList.push(newMaterial);
  }
}

export function makeResult(
  itemList: CreateItemDto[],
  marketList: Market[],
  materials: Material[],
) {
  const materialList: Material[] = [];
  let treeList: Material[] = [];

  for (const material of materials) {
    if (
      !itemList.find(({ name }) => name === material.name) &&
      !marketList.find(({ name }) => name === material.name)
    ) {
      throw new BadRequestException('하위 재료에 잘못된 물품명이 있습니다.');
    }

    if (material.base) {
      makeBase({ material, materialList });
    } else {
      treeList.push(material);
    }
  }

  while (treeList.length !== 0) {
    for (const item of itemList) {
      if (treeList.length > 0 && treeList[0].name === item.name) {
        for (const material of item.materials) {
          if (treeList[0].base) {
            makeBase({ material, materialList, count: treeList[0].count });
            treeList = treeList.slice(1);
          } else {
            treeList.push({
              ...material,
              count: treeList[0].count * material.count,
            });
          }
        }
        treeList = treeList.slice(1);
        break;
      }
    }
    if (treeList.length > 0 && treeList[0].base) {
      makeBase({ material: treeList[0], materialList });
      treeList = treeList.slice(1);
    }
  }

  const prices: number[] = [];
  for (const b of materialList) {
    for (const m of marketList) {
      if (b.name === m.name) {
        prices.push(b.count * m.price);
      }
    }
  }
  return {
    names: materialList.map((b) => b.name).toString(),
    counts: materialList.map((b) => b.count).toString(),
    prices: prices.toString(),
    totalPrice: prices.reduce((acc, cur) => (acc += cur), 0),
  };
}

export function parseResults(
  resultList: Result[],
  count: number,
  itemList: CreateItemDto[],
) {
  return resultList.map((result) => {
    const { names, prices, counts, ...rest } = result;
    const nameList = names.split(',');
    const priceList = prices.split(',');
    const countList = counts.split(',');

    const rates = [1, 1.039, 1.156, 1.35, 1622];
    const rate = count < 5 ? rates[count - 1] : 1.613666 + 0.001555;

    const item = itemList.find((i) => i.name === result.name);

    return {
      ...rest,
      item: {
        ...item,
        materials: item.materials.map((material) => ({
          ...material,
          count: material.count * count,
        })),
      },
      craftingPrice: Math.floor(Number(result.craftingPrice) * count * rate),
      materials: Array.from({ length: nameList.length }, (_, index) => ({
        name: nameList[index],
        price: Number(priceList[index]) * count,
        count: Number(countList[index]) * count,
      })),
      totalPrice: result.totalPrice * count,
    };
  });
}
