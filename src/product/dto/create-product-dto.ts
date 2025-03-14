import { Category } from 'src/product/type/Category';
import { Tool } from 'src/product/type/Tool';

export class CreateProductDto {
  name: string;
  level: number;
  tool: Tool;
  craftingPrice: number;
  category: Category;
}
