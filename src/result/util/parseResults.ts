/* eslint-disable @typescript-eslint/no-unused-vars */
import { Result } from 'src/result/entities/result.entity';

export function parseResult(result: Result, count: number) {
  const { names, prices, counts, product_id, product, ...rest } = result;
  const nameList = names.split(',');
  const priceList = prices.split(',');
  const countList = counts.split(',');

  const rates = [1, 1.039, 1.156, 1.35, 1622];
  const rate = count < 5 ? rates[count - 1] : 1.613666 + 0.001555;

  return {
    ...rest,
    name: product.name,
    level: product.level,
    tool: product.tool,
    product: {
      ...product,
      materials: product.materials.map((material) => ({
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
}

export function parseResults(results: Result[], count: number) {
  return results.map((result) => parseResult(result, count));
}
