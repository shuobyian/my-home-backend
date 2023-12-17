/* eslint-disable @typescript-eslint/no-unused-vars */
import { BadRequestException } from '@nestjs/common';
import { Market } from 'src/market/entities/market.entity';
import { ReadProductDto } from 'src/product/dto/read-product-dto';
import { Result } from 'src/result/entities/result.entity';
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

export function makeResult(
  products: ReadProductDto[],
  markets: Market[],
  _materials: Material[],
) {
  const materials: Material[] = [];
  let treeList: Material[] = [];

  for (const material of _materials) {
    if (
      !products.find(({ name }) => name === material.name) &&
      !markets.find(({ name }) => name === material.name)
    ) {
      throw new BadRequestException('하위 재료에 잘못된 물품명이 있습니다.');
    }

    if (material.basic) {
      makeBasic({ material, materials: materials });
    } else {
      treeList.push(material);
    }
  }

  while (treeList.length !== 0) {
    for (const product of products) {
      if (treeList.length > 0 && treeList[0].name === product.name) {
        for (const material of product.materials) {
          if (treeList[0].basic) {
            makeBasic({ material, materials, count: treeList[0].count });
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
    if (treeList.length > 0 && treeList[0].basic) {
      makeBasic({ material: treeList[0], materials });
      treeList = treeList.slice(1);
    }
  }

  const prices: number[] = [];
  for (const b of materials) {
    for (const m of markets) {
      if (b.name === m.name) {
        prices.push(b.count * m.price);
      }
    }
  }
  return {
    names: materials.map((b) => b.name).toString(),
    counts: materials.map((b) => b.count).toString(),
    prices: prices.toString(),
    totalPrice: prices.reduce((acc, cur) => (acc += cur), 0),
  };
}

export function parseResults(
  results: Result[],
  count: number,
  products: ReadProductDto[],
) {
  return results.map((result) => {
    const { names, prices, counts, product_id, ...rest } = result;
    const nameList = names.split(',');
    const priceList = prices.split(',');
    const countList = counts.split(',');

    const rates = [1, 1.039, 1.156, 1.35, 1622];
    const rate = count < 5 ? rates[count - 1] : 1.613666 + 0.001555;

    const { materials, ...product } = products.find(
      (i) => i.name === result.name,
    );

    return {
      ...rest,
      product: {
        ...product,
        materials: materials.map((material) => ({
          name: material.name,
          basic: material.basic,
          count: material.count * count,
        })),
      },
      craftingPrice: Math.floor(
        Number(result.product.craftingPrice) * count * rate,
      ),
      materials: Array.from({ length: nameList.length }, (_, index) => ({
        name: nameList[index],
        price: Number(priceList[index]) * count,
        count: Number(countList[index]) * count,
      })),
      totalPrice: result.totalPrice * count,
    };
  });
}
