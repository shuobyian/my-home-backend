import { CreateProductDto } from 'src/product/dto/create-product-dto';

export class UpdateProductDto extends CreateProductDto {
  id: number;
  materials: {
    name: string;
    basic: boolean;
    count: number;
  }[];
}
