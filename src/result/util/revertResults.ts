import { ReadResultDto } from 'src/result/dto/read-result-dto';

export function parseUpdateResult(result: ReadResultDto) {
  const { materials } = result;

  const prices = materials.map((material) => material.price);

  return {
    prices: prices.join(','),
    totalPrice: prices.reduce((acc, cur) => (acc += cur), 0),
  };
}
