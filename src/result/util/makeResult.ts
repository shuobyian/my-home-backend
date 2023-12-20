import { BadRequestException } from '@nestjs/common';
import { Market } from 'src/market/entities/market.entity';
import { ReadProductDto } from 'src/product/dto/read-product-dto';
import { Material } from 'src/result/type/Material';
import { makeBasic } from 'src/result/util/makeBasic';

export function makeResult(
  dbProducts: ReadProductDto[],
  dbMarkets: Market[],
  materials: Material[],
) {
  const endMaterials: Material[] = materials.filter(({ basic }) => basic);
  let treeList: Material[] = materials.filter(({ basic }) => !basic);

  const nameList = [
    ...dbProducts.map(({ name }) => name),
    ...dbMarkets.map(({ name }) => name),
  ];
  if (!materials.every(({ name }) => nameList.includes(name))) {
    throw new BadRequestException('하위 재료에 잘못된 물품명이 있습니다.');
  }

  while (treeList.length !== 0) {
    for (const product of dbProducts) {
      if (treeList.length > 0 && treeList[0].name === product.name) {
        for (const material of product.materials) {
          if (treeList[0].basic) {
            makeBasic({ material, endMaterials, count: treeList[0].count });
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
    if (treeList?.[0].basic) {
      makeBasic({ material: treeList[0], endMaterials });
      treeList = treeList.slice(1);
    }
  }

  const prices: number[] = [];
  for (const b of endMaterials) {
    for (const m of dbMarkets) {
      if (b.name === m.name) {
        prices.push(b.count * m.price);
      }
    }
  }
  return {
    names: endMaterials.map((b) => b.name).toString(),
    counts: endMaterials.map((b) => b.count).toString(),
    prices: prices.toString(),
    totalPrice: prices.reduce((acc, cur) => (acc += cur), 0),
  };
}
