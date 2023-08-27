import { Tool } from 'src/item/type/Tool';

export class CreateItemDto {
  name: string;
  level: number;
  tool: Tool;
  craftingPrice: number;
  materials: {
    name: string;
    base: boolean;
    count: number;
  }[];
}
