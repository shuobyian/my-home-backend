import { ReadProductDto } from 'src/product/dto/read-product-dto';

export interface Item {
  name: ReadProductDto['name'];
  materials: ReadProductDto['materials'];
}
