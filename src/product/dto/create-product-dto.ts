import { Tool } from 'src/product/type/Tool';

export class CreateProductDto {
  name: string;
  level: number;
  tool: Tool;
  craftingPrice: number;
}
