import { BadRequestException } from '@nestjs/common';
import { Market } from 'src/market/entities/market.entity';
import { ReadProductDto } from 'src/product/dto/read-product-dto';
import { Material } from 'src/result/type/Material';
import { makeBasic } from 'src/result/util/makeBasic';

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
